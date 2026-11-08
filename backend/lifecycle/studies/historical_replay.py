"""Dynamic historical lifecycle portfolio replay: one dated investor, month by month, point-in-time.

Unlike the Monte Carlo studies (thousands of paths, a precomputed target schedule), this study follows ONE
investor through actual history. Every month the target allocation is recomputed from the investor's
*current* state (age, salary, wealth, actual holdings, contributions, human capital, retirement liabilities,
funding ratio) and from market information available on that date, and the canonical holdings ledger
executes exactly one month (`ledger.simulate` with starting holdings `h0` and global month `t0`; a
whole-horizon run and 1-month sequential calls are identical, see tests/test_sequential_ledger.py).

Timing convention (decision date D_t = first day of month t; returns R_t are realised during month t):
  * asset returns are usable through month t-1 (market prices are known at month end);
  * CPI for month m is published ~15 days after m, so at D_t inflation is known through t-2;
  * yields (FRED CMT/TIPS, monthly) are available one day after month end, i.e. through t-1;
  * a sleeve is eligible at D_t only if it has `min_history_months` valid monthly returns ending at t-1
    and the instrument still trades in month t; nothing is back-filled or spliced;
  * every estimate (means, covariances, volatilities, trends, regime model) uses only rows in that
    information set; the regime model is refitted every `refit_months` on an expanding window.
Order within month t (the ledger's order): planned flows (contribution / desired draw) -> fund flows toward
the target -> trading decision on post-flow weights (rebalancing rule) -> trades + costs -> earn R_t.

Three layers are kept separate and recorded: STRATEGIC target (policy objective), TACTICAL deviation
(bounded overlay) and EXECUTION (the rebalancing rule decides whether and what to trade).

The historical section is nominal dollars; real values deflate by realised CPI into dollars of the last
historical month. The forward continuation starts from the exact final holdings, age and salary and runs
bootstrap scenarios (real, in last-month dollars) through age 95 with the same state-dependent policies.
Research output, not advice.
"""
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from pydantic import Field

from lifecycle.data import panel
from lifecycle.data.series import SERIES
from lifecycle.engine.lifecycle import ledger as L
from lifecycle.engine.lifecycle.utility import ce_from_utility
from lifecycle.engine.scenarios.base import to_features
from lifecycle.engine.scenarios.markov_switching import MarkovSwitching, _logpdf_all, hamilton_filter
from lifecycle.studies import common as S

CANDIDATES = ("us_eq", "intl_eq", "em_eq", "ust_10y", "ust_30y", "tips", "ig_credit", "hy_credit", "gold",
              "commodities", "fx_basket", "tbill")
BLOCK_OF = {"equity": "growth", "rates": "duration", "credit": "credit", "currency": "real", "commodities": "real",
            "real_assets": "real", "cash": "cash"}
POLICIES = {
    "sixty_forty": ("static", "Static 60/40 (US equity / 10Y Treasury)"),
    "target_date": ("glidepath", "Target-date glidepath (equity = (110 - age)%, bounded 30-90%)"),
    "pp_classic": ("static", "Classic Permanent Portfolio (25% equity / long Treasury / gold / cash)"),
    "pp_multi_asset": ("static", "Generalised multi-asset all-weather (25% growth / duration / real & currency / cash)"),
    "risk_parity": ("risk", "Static risk parity (equal risk contribution, point-in-time covariance)"),
    "trend_tsmom": ("trend", "Trend: risk parity with 12-month time-series momentum to cash"),
    "inverse_vol": ("risk", "Inverse trailing volatility"),
    "vol_target": ("risk", "Volatility-targeted 60/40 (12-month risk, exposure scaled down to a 10% target)"),
    "regime_adaptive": ("regime", "Regime-adaptive CRRA mean-variance (filtered Markov regimes)"),
    "crra_parametric": ("utility", "CRRA mean-variance with trend and volatility tilts"),
    "lifecycle_adaptive": ("lifecycle", "Lifecycle-adaptive: total wealth (human capital), liability hedge, funding ratio"),
}
EVENTS = [("2008-09", "Lehman Brothers bankruptcy"), ("2009-03", "Equity market trough"),
          ("2013-05", "Taper tantrum"), ("2020-03", "COVID-19 crash"), ("2022-01", "2022 inflation / rate shock begins"),
          ("2022-10", "2022 bond and equity trough")]


class ReplayInvestor(S.Frozen):
    start_age: float = Field(20.0, ge=18, le=80)
    initial_wealth: float = Field(10_000.0, ge=0)
    salary: float = Field(45_000.0, ge=0)                    # nominal at the start date
    real_wage_growth_young: float = Field(0.04, ge=0, le=0.1)  # real growth at age 20, declining to 0 at 55
    savings_rate: float = Field(0.15, ge=0, le=0.8)
    retirement_age: float = Field(65.0, ge=40, le=80)
    spending_ratio: float = Field(0.70, ge=0, le=1.5)        # desired retirement spending / final salary
    pension_ratio: float = Field(0.30, ge=0, le=1.0)         # pension / final salary (not portfolio-funded)
    final_age: float = Field(95.0, ge=70, le=105)
    sex: str = "unisex"


class ReplayRebalance(S.Frozen):
    mode: str = Field("absolute_band", pattern="^(absolute_band|calendar)$")
    band: float = Field(0.05, gt=0, le=0.3)
    cadence_months: int = Field(12, ge=1, le=24)
    funding: str = Field("cash_flow_targeting", pattern="^(cash_flow_targeting|proportional)$")


class HistoricalReplaySpec(S.Frozen):
    start: str = "2007-01"
    end: str | None = None                                  # None = latest month with every needed observation
    universe_mode: str = Field("fixed", pattern="^(fixed|expanding)$")
    candidates: tuple[str, ...] = CANDIDATES
    investor: ReplayInvestor = Field(default_factory=ReplayInvestor)
    preferences: S.StudyPrefs = Field(default_factory=S.StudyPrefs)
    costs: S.StudyCosts = Field(default_factory=lambda: S.StudyCosts(commission_bps=1, half_spread_bps=2))
    rebalance: ReplayRebalance = Field(default_factory=ReplayRebalance)
    policies: tuple[str, ...] = tuple(POLICIES)
    min_history_months: int = Field(36, ge=12, le=240)
    estimation_window_months: int | None = Field(120, ge=24, le=600)   # None = expanding
    refit_months: int = Field(12, ge=1, le=60)
    trend_months: int = Field(12, ge=3, le=24)
    vol_months: int = Field(12, ge=6, le=36)
    target_vol: float = Field(0.10, gt=0.01, le=0.3)          # vol_target scales the 60/40 benchmark
    tactical_limit: float = Field(0.10, ge=0, le=0.3)
    max_sleeve: float = Field(0.60, gt=0.1, le=1.0)
    mean_shrinkage: float = Field(0.5, ge=0, le=1)
    prior_sharpe: float = Field(0.25, ge=0, le=1)
    forward_paths: int = Field(500, ge=0, le=5000)
    forward_block_months: int = Field(12, ge=1, le=60)
    seed: int = 20261107
    experiments: bool = True
    label: str | None = None


# ============================================================================== point-in-time data
@dataclass
class History:
    dates: pd.DatetimeIndex                     # month ends of the replay (decision at the start of each)
    R: pd.DataFrame                             # nominal monthly total returns (NaN where not traded)
    avail: pd.DataFrame                         # available_from timestamps of each return row
    cpi: pd.Series                              # monthly CPI inflation
    cpi_avail: pd.Series
    states: pd.DataFrame                        # yields, spreads, VIX (month-end values)
    state_avail: pd.DataFrame
    not_ingested: list[str] = field(default_factory=list)


def _wide(ids: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = panel.panel()
    sub = p[p["series_id"].isin(ids)]
    v = sub.pivot_table(index="month_end", columns="series_id", values="value", aggfunc="last")
    a = sub.pivot_table(index="month_end", columns="series_id", values="available_from", aggfunc="last")
    return v.reindex(columns=ids), a.reindex(columns=ids)


def load_history(spec: HistoricalReplaySpec) -> History:
    present = [c for c in spec.candidates if panel.has_series(c)]
    missing = [c for c in spec.candidates if c not in present]
    if "tbill" not in present:
        raise S.IncompatibleUniverse("the replay needs T-bills (cash)")
    R, A = _wide(present)
    # a month's market total return is observable at that month end (the price is public); vendor file lags
    # (e.g. CRSP/WRDS ingestion dates) are kept in the catalog but do not hide prices a trader could see
    A = pd.DataFrame(np.where(R.notna().to_numpy(), np.array(R.index, dtype="datetime64[ns]")[:, None], np.datetime64("NaT")),
                     index=R.index, columns=R.columns)
    st_ids = [s for s in ("y_tb3ms", "y_dgs10", "y_dgs30", "y_dfii10", "y_aaa", "y_baa", "s_vixcls") if panel.has_series(s)]
    Sv, Sa = _wide(st_ids)
    cpi_v, cpi_a = _wide(["cpi_nsa"])
    R.index = pd.DatetimeIndex(R.index)
    start = pd.Timestamp(spec.start + "-01") + pd.offsets.MonthEnd(0)
    last_obs = min(R["us_eq"].last_valid_index(), R["tbill"].last_valid_index(), cpi_v["cpi_nsa"].last_valid_index())
    end = last_obs if spec.end is None else min(pd.Timestamp(spec.end + "-01") + pd.offsets.MonthEnd(0), last_obs)
    if start >= end:
        raise ValueError("start must precede the last available observation (%s)" % last_obs.date())
    dates = pd.date_range(start, end, freq="ME")
    return History(dates=dates, R=R, avail=A, cpi=cpi_v["cpi_nsa"], cpi_avail=cpi_a["cpi_nsa"], states=Sv,
                   state_avail=Sa, not_ingested=missing)


def info_returns(h: History, decision: pd.Timestamp, month_end_prev: pd.Timestamp) -> pd.DataFrame:
    """Returns known at the decision date: rows through t-1 whose available_from <= decision."""
    R = h.R.loc[:month_end_prev]
    A = h.avail.loc[:month_end_prev]
    ok = A.le(decision) | A.isna()          # rows without a recorded lag are market prices known at month end
    return R.where(ok)


def info_value(v: pd.Series, a: pd.Series, decision: pd.Timestamp) -> tuple[float | None, pd.Timestamp | None]:
    vv = v.dropna()
    aa = a.reindex(vv.index)
    ok = vv[(aa <= decision).fillna(False)]
    if ok.empty:
        return None, None
    return float(ok.iloc[-1]), ok.index[-1]


# ============================================================================== optimisation helpers
def proj_capped_simplex(v: NDArray[np.float64], cap: NDArray[np.float64]) -> NDArray[np.float64]:
    lo, hi = v.min() - 1.0, v.max()
    for _ in range(100):
        tau = 0.5 * (lo + hi)
        s = np.clip(v - tau, 0, cap).sum()
        if s > 1:
            lo = tau
        else:
            hi = tau
    return np.clip(v - 0.5 * (lo + hi), 0, cap)


def mv_opt(mu: NDArray[np.float64], cov: NDArray[np.float64], gamma: float, cap: float) -> NDArray[np.float64]:
    """argmax w'mu - gamma/2 w'Cov w, long-only, sum 1, each weight <= cap (projected gradient)."""
    n = len(mu)
    caps = np.full(n, max(cap, 1.0 / n + 1e-9))
    w = np.full(n, 1.0 / n)
    lmax = max(np.linalg.eigvalsh(cov).max() * gamma, 1e-6)
    step = 1.0 / lmax
    for _ in range(500):
        w_new = proj_capped_simplex(w + step * (mu - gamma * cov @ w), caps)
        if np.abs(w_new - w).max() < 1e-9:
            w = w_new
            break
        w = w_new
    return w


def erc(cov: NDArray[np.float64]) -> NDArray[np.float64]:
    n = cov.shape[0]
    w = np.ones(n) / n
    for _ in range(500):
        rc = w * (cov @ w)
        w = w * (rc.sum() / n / np.maximum(rc, 1e-18)) ** 0.5
        w = w / w.sum()
    return w


def par_duration(y: float, years: float) -> float:
    y = max(y, 1e-4)
    return float((1 - (1 + y / 2) ** (-2 * years)) / y)


def wage_growth(age: float, young: float) -> float:
    return max(0.0, young * (1 - (age - 20.0) / 35.0)) if age < 55 else 0.0


# ============================================================================== investor state
def survival(age: float, sex: str) -> NDArray[np.float64]:
    """P(alive at integer ages a0..109 | alive at age), from the SSA period table."""
    from lifecycle.config import processed_dir
    path = processed_dir() / "life_table.parquet"
    if path.exists():
        lt = pd.read_parquet(path)
    else:   # synthetic CI mode: Gompertz fallback (flagged in the methodology)
        ages = np.arange(120)
        lt = pd.DataFrame({"age": ages, "q_" + sex: np.minimum(1.0, 0.0001 * np.exp(0.085 * ages))})
    q = lt.set_index("age")["q_" + sex].reindex(range(0, 120)).ffill().to_numpy()
    a0 = int(np.floor(age))
    p = np.cumprod(np.r_[1.0, 1 - q[a0:109]])
    return p


_SURV: dict[tuple[int, str], NDArray[np.float64]] = {}


def surv(age: float, sex: str) -> NDArray[np.float64]:
    k = (int(np.floor(age)), sex)
    if k not in _SURV:
        _SURV[k] = survival(age, sex)
    return _SURV[k]


def liabilities(inv: ReplayInvestor, age: float, salary_real: float, real_rate: float) -> dict[str, float]:
    """PV (current dollars) of desired portfolio-funded retirement spending and of future contributions."""
    p = surv(age, inv.sex)
    r = min(max(real_rate, -0.01), 0.06)
    a0 = int(np.floor(age))
    sal = salary_real
    contribs, cf_l, ages = [], [], []
    final = salary_real
    for x in range(a0, 110):
        k = x - a0
        if x < inv.retirement_age:
            contribs.append(p[k] * inv.savings_rate * sal / (1 + r) ** k)
            final = sal
            sal *= 1 + wage_growth(x, inv.real_wage_growth_young)
        if x >= inv.retirement_age and x < 100:
            net = max(inv.spending_ratio - inv.pension_ratio, 0.0) * final
            cf_l.append(p[k] * net / (1 + r) ** k)
            ages.append(k)
    pv_l = float(np.sum(cf_l))
    dur = float(np.dot(ages, cf_l) / pv_l / (1 + r)) if pv_l > 0 else 0.0
    return {"pv_liabilities": pv_l, "human_capital": float(np.sum(contribs)), "liability_duration": dur,
            "final_salary_real": float(final), "annual_net_spend_real": max(inv.spending_ratio - inv.pension_ratio, 0.0) * float(final),
            "real_rate": r}


# ============================================================================== market state
class MarketModel:
    """Point-in-time estimates; refits the regime model every `refit_months` on an expanding window."""

    def __init__(self, spec: HistoricalReplaySpec, h: History) -> None:
        self.spec = spec
        self.h = h
        self.ms: MarkovSwitching | None = None
        self.ms_fit_end: pd.Timestamp | None = None
        self.ms_months = 0

    def snapshot(self, t: int) -> dict[str, Any]:
        spec, h = self.spec, self.h
        me = h.dates[t]
        prev = me - pd.offsets.MonthEnd(1)
        D = prev + pd.Timedelta(days=1)                  # decision date: first day of month t
        Rk = info_returns(h, D, prev)
        cands = [c for c in h.R.columns]
        elig, hist_len = [], {}
        for c in cands:
            col = Rk[c]
            last = col.last_valid_index()
            if last is None or last < prev:
                hist_len[c] = 0
                continue
            run = col.loc[:prev].iloc[::-1]
            n = int(run.notna().cumprod().sum())
            hist_len[c] = n
            trades_now = not np.isnan(h.R.at[me, c]) if me in h.R.index else False
            if n >= spec.min_history_months and trades_now:
                elig.append(c)
        if "tbill" not in elig:
            raise S.IncompatibleUniverse("T-bill (cash) returns are missing for %s or have fewer than %d months of history "
                                         "before it; the replay needs a cash sleeve every month" % (me.date(), spec.min_history_months))
        win = Rk[elig].dropna()
        if spec.estimation_window_months is not None:
            win = win.iloc[-spec.estimation_window_months:]
        X = win.to_numpy()
        rf_m = float(Rk["tbill"].dropna().iloc[-1])
        ex = X - X[:, [elig.index("tbill")]]
        cov = np.cov(X, rowvar=False) * 12
        cov = 0.5 * cov + 0.5 * np.diag(np.diag(cov)) + 1e-8 * np.eye(len(elig))
        vol = np.sqrt(np.diag(cov))
        mu_ex = (1 - spec.mean_shrinkage) * ex.mean(axis=0) * 12 + spec.mean_shrinkage * spec.prior_sharpe * vol
        mu_ex[elig.index("tbill")] = 0.0
        tr = Rk[elig].iloc[-spec.trend_months:]
        trend = (np.prod(1 + tr.to_numpy(), axis=0) - np.prod(1 + tr["tbill"].to_numpy()))
        vv = Rk[elig].iloc[-spec.vol_months:].to_numpy()
        vol_short = vv.std(axis=0, ddof=1) * np.sqrt(12)
        st = {}
        for sid in h.states.columns:
            val, when = info_value(h.states[sid], h.state_avail[sid], D)
            st[sid] = val
        # CPI is usable only after its publication lag (at least 15 days, whatever a source records)
        lagged = pd.concat([h.cpi_avail.reindex(h.cpi.index), pd.Series(h.cpi.index + pd.Timedelta(days=15), index=h.cpi.index)],
                           axis=1).max(axis=1)
        cpi_known = h.cpi[(lagged <= D).fillna(False)]
        last12 = cpi_known[cpi_known.index > cpi_known.index[-1] - pd.DateOffset(months=12)] if len(cpi_known) else cpi_known
        infl12 = (float(np.prod(1 + last12.to_numpy()) ** (12 / len(last12)) - 1)    # annualised over the observed months
                  if len(last12) >= 9 else None)
        real_rate = st.get("y_dfii10") if st.get("y_dfii10") is not None else (
            (st.get("y_dgs10") or 0.04) - (infl12 if infl12 is not None else 0.02))
        corr = None
        if "us_eq" in elig and "ust_10y" in elig:
            c36 = Rk[["us_eq", "ust_10y"]].dropna().iloc[-36:]
            corr = float(c36.corr().iloc[0, 1]) if len(c36) >= 24 else None
        regime = self._regime(t, D, cpi_known, Rk)
        return {"date": me, "decision_date": D, "eligible": elig, "history_months": hist_len, "cov": cov, "vol": vol,
                "mu_ex": mu_ex, "rf": rf_m * 12, "trend": trend, "vol_short": vol_short, "window": [str(win.index[0].date()), str(win.index[-1].date())],
                "n_window": len(win), "states": st, "infl12": infl12, "real_rate": float(real_rate), "corr_eq_bond_36m": corr,
                "regime": regime, "info_last_return": str(prev.date()), "info_last_cpi": str(cpi_known.index[-1].date()) if len(cpi_known) else None,
                "win_returns": win}

    def _regime(self, t: int, D: pd.Timestamp, cpi_known: pd.Series, Rk: pd.DataFrame) -> dict[str, Any] | None:
        """2-state Markov model on real US equity / 10Y Treasury returns + CPI, expanding window, PIT."""
        cols = ["us_eq", "ust_10y"]
        if any(c not in Rk.columns for c in cols):
            return None
        frame = Rk[cols].join(cpi_known.rename("cpi"), how="inner").dropna()
        frame = frame.iloc[-480:]
        if len(frame) < 120:
            return None
        real = (1 + frame[cols].to_numpy()) / (1 + frame[["cpi"]].to_numpy()) - 1
        infl = frame["cpi"].to_numpy()
        if self.ms is None or self.ms_months >= self.spec.refit_months:
            self.ms = MarkovSwitching(real, infl, k=2)
            self.ms_fit_end = frame.index[-1]
            self.ms_months = 0
        self.ms_months += 1
        ld = _logpdf_all(to_features(real, infl), self.ms.mu, self.ms.sigma)
        filt, _pred, _ = hamilton_filter(ld, self.ms.P, np.full(2, 0.5))
        gap = max(1, (D.to_period("M") - frame.index[-1].to_period("M")).n)
        prob = filt[-1] @ np.linalg.matrix_power(self.ms.P, gap)
        return {"p": prob.tolist(), "p_high_inflation": float(prob[1]), "filtered": filt, "index": frame.index,
                "fit_end": str(self.ms_fit_end.date()), "info_end": str(frame.index[-1].date()),
                "mean_inflation_by_regime": (self.ms.mu[:, -1] * 12).tolist()}


# ============================================================================== policies
def blocks(elig: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for i, c in enumerate(elig):
        cls = SERIES[c].asset_class if c in SERIES else "other"
        out.setdefault(BLOCK_OF.get(cls, "real"), []).append(i)
    return out


def target(policy: str, m: dict[str, Any], st: dict[str, Any], spec: HistoricalReplaySpec) -> dict[str, Any] | None:
    """Strategic target, tactical deviation and final target over the eligible sleeves (None = unavailable)."""
    elig = m["eligible"]
    n = len(elig)
    ix = {c: i for i, c in enumerate(elig)}
    cash = ix["tbill"]
    gamma = spec.preferences.gamma
    cov, vol = m["cov"], m["vol"]
    mu = m["mu_ex"] + m["rf"]
    risky = [i for i in range(n) if i != cash]
    strat = np.zeros(n)
    tact = np.zeros(n)
    notes: dict[str, Any] = {}
    binding: list[str] = []

    def put(d: dict[str, float]) -> NDArray[np.float64]:
        v = np.zeros(n)
        for k, x in d.items():
            if k not in ix:
                return None
            v[ix[k]] = x
        return v / v.sum()

    if policy == "sixty_forty":
        strat = put({"us_eq": 0.6, "ust_10y": 0.4})
    elif policy == "target_date":
        e = float(np.clip((110 - st["age"]) / 100, 0.3, 0.9))
        d = {"us_eq": 0.7 * e, "intl_eq": 0.3 * e} if "intl_eq" in ix else {"us_eq": e}
        d["ust_10y"] = 1 - e
        strat = put(d)
        notes["equity_share"] = e
    elif policy == "pp_classic":
        if "gold" not in ix or "ust_30y" not in ix:
            return None
        strat = put({"us_eq": 0.25, "ust_30y": 0.25, "gold": 0.25, "tbill": 0.25})
    elif policy == "pp_multi_asset":
        b = blocks(elig)
        for name in ("growth", "duration", "real", "cash"):
            idx = b.get(name, [])
            if not idx:
                strat[cash] += 0.25
                binding.append("block '%s' has no eligible sleeve: its 25%% goes to cash" % name)
                continue
            iv = 1 / np.maximum(vol[idx], 1e-4)
            strat[idx] += 0.25 * iv / iv.sum()
    elif policy == "vol_target":
        strat = put({"us_eq": 0.6, "ust_10y": 0.4})
        if strat is None:
            return None
        corr = cov / np.sqrt(np.outer(np.diag(cov), np.diag(cov)))
        cov_s = corr * np.outer(m["vol_short"], m["vol_short"])     # short-window (12m) risk, long-window correlation
        pv = float(np.sqrt(strat @ cov_s @ strat))
        scale = min(1.0, spec.target_vol / max(pv, 1e-6))
        tact = strat * (scale - 1)
        tact[cash] += 1 - scale
        notes.update({"ex_ante_vol_12m": pv, "scale": scale, "target_vol": spec.target_vol})
    elif policy in ("risk_parity", "trend_tsmom"):
        strat[risky] = erc(cov[np.ix_(risky, risky)])
        if policy == "trend_tsmom":
            off = [i for i in risky if m["trend"][i] < 0]
            for i in off:
                tact[i] -= strat[i]
                tact[cash] += strat[i]
            notes["sleeves_off_trend"] = [elig[i] for i in off]
    elif policy == "inverse_vol":
        iv = np.zeros(n)
        iv[risky] = 1 / np.maximum(m["vol_short"][risky], 1e-4)
        strat = iv / iv.sum()
    elif policy == "regime_adaptive":
        rg = m["regime"]
        if rg is None:
            return None
        mu_r, cov_r = regime_moments(m, rg)
        strat = mv_opt(mu_r, cov_r, gamma, spec.max_sleeve)
        notes.update({"p_high_inflation": rg["p_high_inflation"]})
    elif policy == "crra_parametric":
        strat = mv_opt(mu, cov, gamma, spec.max_sleeve)
        g = blocks(elig).get("growth", [])
        if g and spec.tactical_limit > 0:
            gw = strat[g].sum()
            tr = float(np.sign(np.dot(m["trend"][g], strat[g]) / max(gw, 1e-12)))
            vr = float(np.dot(m["vol_short"][g], strat[g]) / max(np.dot(vol[g], strat[g]), 1e-12))
            mult = np.exp(0.25 * tr) * vr ** -0.5
            new = np.clip(gw * mult, gw - spec.tactical_limit, gw + spec.tactical_limit)
            new = float(np.clip(new, 0, min(1.0, gw + strat[cash])))
            d = new - gw
            if gw > 0:
                tact[g] = strat[g] / gw * d
            tact[cash] -= d
            notes.update({"growth_trend_sign": tr, "vol_ratio": vr})
    elif policy == "lifecycle_adaptive":
        strat, tact, notes = lifecycle_target(m, st, spec)
    else:
        raise ValueError("unknown policy " + policy)
    if strat is None:
        return None
    final = np.maximum(strat + tact, 0)
    final = final / final.sum()
    for i in range(n):
        if final[i] >= spec.max_sleeve - 1e-6 and policy in ("regime_adaptive", "crra_parametric", "lifecycle_adaptive"):
            binding.append("%s at the %.0f%% sleeve cap" % (elig[i], spec.max_sleeve * 100))
    return {"strategic": strat, "tactical": final - strat, "final": final, "notes": notes, "binding": binding}


def regime_moments(m: dict[str, Any], rg: dict[str, Any]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Regime-mixture mean and covariance of the eligible sleeves (filtered probabilities as weights)."""
    win = m["win_returns"]
    filt = pd.DataFrame(rg["filtered"], index=rg["index"]).reindex(win.index).dropna()
    X = win.loc[filt.index].to_numpy()
    if len(X) < 24:
        return m["mu_ex"] + m["rf"], m["cov"]
    p = np.asarray(rg["p"])
    mus, covs = [], []
    for k in range(2):
        w = filt[k].to_numpy()
        w = w / max(w.sum(), 1e-12)
        mk = (w[:, None] * X).sum(axis=0)
        ck = ((X - mk) * w[:, None]).T @ (X - mk)
        mus.append(mk * 12)
        covs.append(ck * 12)
    mu = sum(p[k] * mus[k] for k in range(2))
    cov = sum(p[k] * (covs[k] + np.outer(mus[k] - mu, mus[k] - mu)) for k in range(2))
    cov = 0.5 * cov + 0.5 * np.diag(np.diag(cov)) + 1e-8 * np.eye(len(mu))
    vol = np.sqrt(np.diag(cov))
    shrunk = m["rf"] + 0.5 * (mu - m["rf"]) + 0.5 * 0.25 * vol
    shrunk[m["eligible"].index("tbill")] = m["rf"]
    return shrunk, cov


def lifecycle_target(m: dict[str, Any], st: dict[str, Any], spec: HistoricalReplaySpec):
    """Strategic: myopic CRRA on total wealth (financial + human capital) with a liability-duration-matched safe
    sleeve whose size grows with liabilities relative to total wealth. Tactical: bounded trend / volatility tilt."""
    elig = m["eligible"]
    n = len(elig)
    ix = {c: i for i, c in enumerate(elig)}
    cash = ix["tbill"]
    gamma = spec.preferences.gamma
    b = blocks(elig)
    risky = sorted(b.get("growth", []) + b.get("credit", []) + b.get("real", []))
    dur = b.get("duration", [])
    mu = m["mu_ex"] + m["rf"]
    cov = m["cov"]
    strat = np.zeros(n)
    tact = np.zeros(n)
    # risky mix: CRRA mean-variance over the risky sleeves; its Merton exposure on TOTAL wealth
    mix = mv_opt(mu[risky], cov[np.ix_(risky, risky)], gamma, min(1.0, spec.max_sleeve / 0.8))
    mu_m = float(mix @ mu[risky])
    var_m = float(mix @ cov[np.ix_(risky, risky)] @ mix)
    alpha = float(np.clip((mu_m - m["rf"]) / (gamma * max(var_m, 1e-6)), 0.0, 1.5))
    W = max(st["wealth"], 1.0)
    tw = W + st["human_capital"]
    s = float(np.clip(alpha * tw / W, 0.0, 1.0))
    # safe bucket: liability hedge share = PV(liabilities) / total wealth, duration-matched
    hedge = float(np.clip(st["pv_liabilities"] / max(tw, 1.0), 0.0, 1.0))
    safe = 1 - s
    durs = {}
    y10 = (m["states"].get("y_dgs10") or 0.04)
    y30 = (m["states"].get("y_dgs30") or y10)
    for c in elig:
        if c == "ust_10y":
            durs[c] = par_duration(y10, 10)
        elif c == "ust_30y":
            durs[c] = par_duration(y30, 30)
        elif c == "tips":
            durs[c] = par_duration(max(m["states"].get("y_dfii10") or 0.01, 1e-3), 10)
    target_d = min(st["liability_duration"], max(durs.values()) if durs else 0.0)
    bond_w = np.zeros(n)
    if dur and durs:
        nominal = [c for c in ("ust_10y", "ust_30y") if c in durs]
        if len(nominal) == 2:
            d1, d2 = durs["ust_10y"], durs["ust_30y"]
            x = float(np.clip((target_d - d1) / max(d2 - d1, 1e-6), 0, 1))
            bond_w[ix["ust_10y"]], bond_w[ix["ust_30y"]] = 1 - x, x
        elif nominal:
            bond_w[ix[nominal[0]]] = 1.0
        if "tips" in ix and st["years_to_retirement"] <= 15:     # real liabilities near retirement: half in TIPS
            bond_w = 0.5 * bond_w
            bond_w[ix["tips"]] += 0.5
    for j, i in enumerate(risky):
        strat[i] = s * mix[j]
    if bond_w.sum() > 0:
        strat += safe * hedge * bond_w
        strat[cash] += safe * (1 - hedge)
    else:
        strat[cash] += safe
    # tactical: bounded shift between the risky sleeves and cash
    g = b.get("growth", [])
    tr = float(np.sign(np.dot(m["trend"][g], strat[g]) / max(strat[g].sum(), 1e-12))) if g else 0.0
    vr = float(np.dot(m["vol_short"][risky], mix) / max(np.dot(np.sqrt(np.diag(cov))[risky], mix), 1e-12))
    d = spec.tactical_limit * (0.5 * tr - 0.5 * float(vr > 1.5))
    d = float(np.clip(d, -s, min(strat[cash], 1 - s)))
    if s > 0:
        for j, i in enumerate(risky):
            tact[i] = d * mix[j]
        tact[cash] -= d
    notes = {"objective": "max E[CRRA(total wealth)] one month ahead (Merton-Bodie-Samuelson) + liability-duration-matched safe sleeve",
             "alpha_total_wealth": alpha, "risky_share": s, "human_capital": st["human_capital"],
             "pv_liabilities": st["pv_liabilities"], "funding_ratio": st["funding_ratio"], "hedge_ratio": hedge,
             "liability_duration": st["liability_duration"], "target_duration": target_d, "risky_mu": mu_m,
             "risky_vol": float(np.sqrt(var_m)), "trend_sign": tr, "vol_ratio": vr, "tactical_shift": d}
    return strat, tact, notes


# ============================================================================== the replay
def _cfg(spec, inv, W, h0, t0, retire_m, spend0, T=1, trace=0, cash_idx=-1, disc=None):
    rb = spec.rebalance
    tr = L.TradingSpec(mode=rb.mode, cadence_months=rb.cadence_months, abs_band=rb.band, check_months=1,
                       funding=rb.funding, commission_bps=spec.costs.commission_bps,
                       half_spread_bps=spec.costs.half_spread_bps, slippage_bps=spec.costs.slippage_bps)
    return L.LedgerConfig(w0=W, retire_m=retire_m, spend_mode=L.SPEND_MODES["fixed_real"], rate=0.0,
                          savings_rate=inv.savings_rate, sched=None, trading=tr,
                          disc=np.ones(T) if disc is None else disc, beq=np.zeros(T), gamma=spec.preferences.gamma,
                          record_years=False, trace_path=trace, cash_index=cash_idx, h0=h0, t0=t0, spend0=spend0)


_SNAPS: dict[tuple, list[dict[str, Any]]] = {}


def market_snapshots(spec: HistoricalReplaySpec, h: History, progress=None) -> list[dict[str, Any]]:
    """Point-in-time market state for every month; depends only on data and estimation settings (cached)."""
    key = (str(h.dates[0]), str(h.dates[-1]), tuple(h.R.columns), spec.min_history_months, spec.estimation_window_months,
           spec.refit_months, spec.trend_months, spec.vol_months, spec.mean_shrinkage, spec.prior_sharpe,
           panel.catalog_hash(), int(pd.util.hash_pandas_object(h.R, index=True).sum()))
    if key not in _SNAPS:
        model = MarketModel(spec, h)
        out = []
        for t in range(len(h.dates)):
            out.append(model.snapshot(t))
            if progress and t % 24 == 0:
                progress("market_state %s" % h.dates[t].date(), 0.05 + 0.25 * t / len(h.dates))
        if len(_SNAPS) > 16:
            _SNAPS.clear()
        _SNAPS[key] = out
    return _SNAPS[key]


def replay(spec: HistoricalReplaySpec, h: History, policies: list[str], progress=None, detail: bool = True,
           ablation: str | None = None) -> dict[str, Any]:
    inv = spec.investor
    cand = list(h.R.columns)
    A = len(cand)
    T = len(h.dates)
    snaps = market_snapshots(spec, h, progress)
    retire_m = int(round((inv.retirement_age - inv.start_age) * 12))
    fixed_set: list[str] | None = None
    if spec.universe_mode == "fixed":
        fixed_set = [c for c in snaps[0]["eligible"] if all(c in s["eligible"] for s in snaps)]
        dropped = sorted(set().union(*[set(s["eligible"]) for s in snaps]) - set(fixed_set))
    else:
        dropped = []
    # CPI index for real accounting (realised, ex post): dollars of the last historical month
    cpi = h.cpi.reindex(h.dates).fillna(0.0)
    idx = np.cumprod(1 + cpi.to_numpy())
    to_real_last = idx[-1] / idx
    out: dict[str, Any] = {}
    for pi, pol in enumerate(policies):
        Wh = np.zeros(A)
        W = inv.initial_wealth
        salary = inv.salary
        spend = 0.0
        rec: dict[str, list] = {k: [] for k in ("w_pre", "strategic", "tactical", "target", "w_post", "trades", "cost",
                                                "reason", "contrib", "draw", "wealth_post", "wealth_end", "holdings_end",
                                                "salary", "age", "funding_ratio", "pv_liabilities", "human_capital",
                                                "notes", "binding", "eligible_added", "eligible_removed", "ex_ante_vol", "rc")}
        prev_elig: list[str] = []
        available = True
        last_tg = None
        for t in range(T):
            m = snaps[t]
            elig = m["eligible"] if fixed_set is None else fixed_set
            if fixed_set is not None:
                m = restrict(m, fixed_set)
            age = inv.start_age + t / 12.0
            if t > 0 and h.dates[t].month == 1:     # January raise: real age profile x known CPI inflation
                salary *= (1 + wage_growth(age - 1, inv.real_wage_growth_young)) * (1 + (m["infl12"] or 0.0))
            lia = liabilities(inv, age, salary, m["real_rate"])
            Wnow = float(Wh.sum()) if t > 0 else W
            st = {"age": age, "wealth": Wnow, "salary": salary, "years_to_retirement": max(inv.retirement_age - age, 0.0),
                  "human_capital": 0.0 if ablation == "no_human_capital" else lia["human_capital"],
                  "pv_liabilities": lia["pv_liabilities"], "liability_duration": lia["liability_duration"],
                  "funding_ratio": (Wnow + lia["human_capital"]) / max(lia["pv_liabilities"], 1.0)}
            if ablation == "no_liability_hedge":
                st["pv_liabilities"] = 0.0
            mm = m
            if ablation == "no_market_signals":
                mm = dict(m)
                mm["trend"] = np.ones_like(m["trend"])
                mm["vol_short"] = m["vol"].copy()
            if ablation == "frozen_target" and last_tg is not None:
                tg = last_tg
            else:
                tg = target(pol, mm, st, spec)
            if tg is None:
                available = False
                break
            last_tg = tg

            def fullvec(v, _e=tuple(elig)):
                return _full(v, list(_e), cand)
            tgt_full = fullvec(tg["final"])
            # month t: nominal returns of the candidates (0 for sleeves not held / not traded)
            r = h.R.loc[h.dates[t]].reindex(cand).to_numpy(dtype=float)
            held_nan = [cand[a] for a in range(A) if np.isnan(r[a]) and Wh[a] > 0]
            forced = []
            for c in held_nan:        # no return series for a held sleeve this month: exit to cash at last value
                a_ = cand.index(c)
                Wh[cand.index("tbill")] += Wh[a_]
                forced.append("%s: no return this month (data gap) - %.0f moved to cash at its last value" % (c, Wh[a_]))
                Wh[a_] = 0.0
            r = np.nan_to_num(r)
            # retirement spending (nominal, CPI-indexed from the real liability model)
            g = t
            if g >= retire_m:
                if spend == 0.0:
                    spend = lia["annual_net_spend_real"] if age >= inv.retirement_age else 0.0
                elif h.dates[t].month == 1:
                    spend *= 1 + (m["infl12"] or 0.0)
            sched = tgt_full[None, None, :]
            cfg = _cfg(spec, inv, W if t == 0 else Wnow, None if t == 0 else Wh[None, :], t, retire_m, spend,
                       cash_idx=cand.index("tbill"))
            cfg.sched = sched
            if ablation == "no_rebalancing":
                cfg.trading = L.TradingSpec(mode="none_buyhold", funding=spec.rebalance.funding,
                                            commission_bps=spec.costs.commission_bps, half_spread_bps=spec.costs.half_spread_bps)
            o = L.simulate(r[None, None, :], np.zeros((1, 1), dtype=np.int64),
                           np.array([[salary / 12.0 if age < inv.retirement_age else 0.0]]),
                           np.zeros((1, 1)), cfg)
            Wh = o.holdings_end[0].copy()
            spend = float(o.spend_end[0]) or spend
            tr_ = o.trace
            rec["w_pre"].append(tr_["pre"][0])
            rec["target"].append(tgt_full)
            rec["strategic"].append(fullvec(tg["strategic"]))
            rec["tactical"].append(fullvec(tg["tactical"]))
            rec["w_post"].append(tr_["post"][0])
            rec["trades"].append(tr_["trade"][0])
            rec["cost"].append(float(tr_["cost"][0]))
            rec["reason"].append(int(tr_["reason"][0]))
            rec["contrib"].append(float(tr_["flow"][0, 2]))
            rec["draw"].append(float(tr_["flow"][0, 1]))
            rec["wealth_post"].append(float(tr_["wealth"][0]))
            rec["wealth_end"].append(float(Wh.sum()))
            rec["holdings_end"].append(Wh.copy())
            rec["salary"].append(salary)
            rec["age"].append(age)
            rec["funding_ratio"].append(st["funding_ratio"])
            rec["pv_liabilities"].append(st["pv_liabilities"])
            rec["human_capital"].append(st["human_capital"])
            rec["notes"].append({**tg["notes"], **({"forced": forced} if forced else {})})
            rec["binding"].append(tg["binding"])
            rec["eligible_added"].append(sorted(set(elig) - set(prev_elig)) if t > 0 else [])
            rec["eligible_removed"].append(sorted(set(prev_elig) - set(elig)))
            covf = m["cov"]
            wp = np.array([tr_["post"][0][cand.index(c)] for c in elig])
            pv = float(np.sqrt(max(wp @ covf @ wp, 0)))
            rc = wp * (covf @ wp) / max(pv ** 2, 1e-12)
            rec["ex_ante_vol"].append(pv)
            rec["rc"].append(_full(rc, elig, cand))
            prev_elig = list(elig)
        if not available:
            out[pol] = {"available": False, "reason": unavailable_reason(pol, h, spec)}
            continue
        out[pol] = summarise(pol, rec, h, to_real_last, spec, detail, cand)
        out[pol]["_state"] = {"holdings": Wh, "salary": salary, "spend": spend, "last_target": rec["target"][-1]}
        if progress:
            progress("replayed %s" % pol, 0.3 + 0.35 * (pi + 1) / len(policies))
    return {"policies": out, "snaps": snaps, "candidates": cand, "fixed_set": fixed_set, "dropped": dropped,
            "to_real_last": to_real_last}


def restrict(m: dict[str, Any], keep: list[str]) -> dict[str, Any]:
    ii = [m["eligible"].index(c) for c in keep]
    mm = dict(m)
    mm["eligible"] = list(keep)
    for k in ("mu_ex", "vol", "trend", "vol_short"):
        mm[k] = m[k][ii]
    mm["cov"] = m["cov"][np.ix_(ii, ii)]
    mm["win_returns"] = m["win_returns"][keep]
    return mm


def _full(v: NDArray[np.float64], elig: list[str], cand: list[str]) -> NDArray[np.float64]:
    out = np.zeros(len(cand))
    for i, c in enumerate(elig):
        out[cand.index(c)] = v[i]
    return out


def unavailable_reason(pol: str, h: History, spec: HistoricalReplaySpec) -> str:
    if pol == "pp_classic":
        if "gold" in h.not_ingested:
            return "gold is not ingested (WRDS GLD); the classic Permanent Portfolio is not evaluated and not proxied"
        return "gold or the 30Y Treasury is not eligible over the replay window"
    if pol == "regime_adaptive":
        return "fewer than 120 months of point-in-time equity / Treasury / CPI history for the regime model"
    return "required sleeves not eligible"


def summarise(pol: str, rec: dict[str, list], h: History, to_real: NDArray[np.float64], spec, detail: bool, cand) -> dict[str, Any]:
    W = np.array(rec["wealth_end"])
    Wpost = np.array(rec["wealth_post"])
    contrib = np.array(rec["contrib"])
    draw = np.array(rec["draw"])
    w0 = spec.investor.initial_wealth
    start_val = np.r_[w0 + contrib[0] - draw[0] - rec["cost"][0], Wpost[1:]]
    twr = W / np.maximum(Wpost, 1e-9) - 1                     # month-t return of the post-trade portfolio
    idx = np.cumprod(1 + twr)
    dd = idx / np.maximum.accumulate(idx) - 1
    cum_c = np.cumsum(contrib)
    gains = W - w0 - cum_c + np.cumsum(draw)
    turnover = np.array([np.abs(x).sum() for x in rec["trades"]]) / np.maximum(start_val, 1e-9)
    nt = int(sum(1 for x in rec["reason"] if x not in (0, 7)))
    years = len(W) / 12
    real_end = float(W[-1])                                    # last-month dollars
    out = {"available": True, "family": POLICIES[pol][0], "label": POLICIES[pol][1],
           "final_wealth": float(W[-1]), "final_wealth_real_last": real_end,
           "total_contributions": float(cum_c[-1]), "investment_gain": float(gains[-1]),
           "twr_annual": float(idx[-1] ** (1 / years) - 1), "vol_annual": float(twr.std(ddof=1) * np.sqrt(12)),
           "max_drawdown": float(dd.min()), "turnover_annual": float(turnover.sum() / years),
           "total_costs": float(np.sum(rec["cost"])), "n_rebalances": nt, "final_funding_ratio": float(rec["funding_ratio"][-1]),
           "worst_month": str(h.dates[int(np.argmin(twr))].date()), "worst_month_return": float(twr.min())}
    if detail:
        r4 = lambda a: np.round(np.asarray(a, dtype=float), 5).tolist()  # noqa: E731
        out["series"] = {
            "wealth": r4(W), "wealth_real": r4(W * to_real), "wealth_post": r4(Wpost), "contrib_cum": r4(cum_c),
            "gains": r4(gains), "twr": r4(twr), "drawdown": r4(dd), "cost": r4(rec["cost"]), "reason": rec["reason"],
            "contrib": r4(contrib), "draw": r4(draw), "salary": r4(rec["salary"]), "funding_ratio": r4(rec["funding_ratio"]),
            "pv_liabilities": r4(rec["pv_liabilities"]), "human_capital": r4(rec["human_capital"]),
            "ex_ante_vol": r4(rec["ex_ante_vol"]), "turnover": r4(turnover),
            "w_pre": r4(rec["w_pre"]), "strategic": r4(rec["strategic"]), "tactical": r4(rec["tactical"]),
            "target": r4(rec["target"]), "w_post": r4(rec["w_post"]), "trades": r4(rec["trades"]),
            "holdings_end": r4(rec["holdings_end"]), "rc": r4(rec["rc"]),
            "notes": [_jsonable(n) for n in rec["notes"]], "binding": rec["binding"],
            "eligible_added": rec["eligible_added"], "eligible_removed": rec["eligible_removed"]}
    return out


def _jsonable(d: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in d.items():
        if isinstance(v, (np.floating, float)):
            out[k] = round(float(v), 6)
        elif isinstance(v, (list, tuple)):
            out[k] = [round(float(x), 6) if isinstance(x, (float, np.floating)) else x for x in v]
        else:
            out[k] = v
    return out


# ============================================================================== forward continuation
def forward_targets(pol: str, m: dict[str, Any], spec: HistoricalReplaySpec, st: dict[str, Any], Wn: NDArray[np.float64],
                    trend: NDArray[np.float64], vs: NDArray[np.float64], pv_base: NDArray[np.float64] | None,
                    p_hi: NDArray[np.float64] | None, cache: dict[str, Any]) -> NDArray[np.float64]:
    """Vectorised form of `target` over N forward paths (market estimates frozen at the boundary; investor state,
    trend, volatility and regime probability path-specific). tests/test_historical_replay.py checks it against
    `target` path by path."""
    N = len(Wn)
    elig = m["eligible"]
    n = len(elig)
    cash = elig.index("tbill")
    risky = [i for i in range(n) if i != cash]
    if pol in ("sixty_forty", "pp_classic", "pp_multi_asset", "risk_parity"):
        if pol not in cache:
            cache[pol] = target(pol, m, st, spec)["final"]
        return np.broadcast_to(cache[pol], (N, n)).copy()
    if pol == "target_date":
        return np.broadcast_to(target(pol, m, st, spec)["final"], (N, n)).copy()
    if pol in ("trend_tsmom", "vol_target"):
        if "rp" not in cache:
            cache["rp"] = target("risk_parity" if pol == "trend_tsmom" else "sixty_forty", m, st, spec)["strategic"]
        base = cache["rp"]
        W = np.broadcast_to(base, (N, n)).copy()
        if pol == "trend_tsmom":
            off = trend < 0
            off[:, cash] = False
            moved = (W * off).sum(axis=1)
            W[off] = 0.0
            W[:, cash] += moved
        else:
            scale = np.minimum(1.0, spec.target_vol / np.maximum(pv_base, 1e-6))
            W = W * scale[:, None]
            W[:, cash] += 1 - scale
        return W
    if pol == "inverse_vol":
        iv = np.zeros((N, n))
        iv[:, risky] = 1 / np.maximum(vs[:, risky], 1e-4)
        return iv / iv.sum(axis=1, keepdims=True)
    if pol == "regime_adaptive":
        if "grid" not in cache:
            grid = np.linspace(0, 1, 11)
            ws = []
            for pg in grid:
                rg = dict(m["regime"])
                rg["p"] = [1 - pg, pg]
                mu_r, cov_r = regime_moments(m, rg)
                ws.append(mv_opt(mu_r, cov_r, spec.preferences.gamma, spec.max_sleeve))
            cache["grid"] = (grid, np.array(ws))
        grid, ws = cache["grid"]
        k = np.clip(p_hi * 10, 0, 9.999)
        lo = np.floor(k).astype(int)
        fr = (k - lo)[:, None]
        return (1 - fr) * ws[lo] + fr * ws[lo + 1]
    if pol == "crra_parametric":
        if "mv" not in cache:
            tg = target(pol, m, st, spec)
            cache["mv"] = tg["strategic"]
        strat = cache["mv"]
        g = blocks(elig).get("growth", [])
        W = np.broadcast_to(strat, (N, n)).copy()
        if g and spec.tactical_limit > 0:
            gw = strat[g].sum()
            tr = np.sign(trend[:, g] @ strat[g] / max(gw, 1e-12))
            vr = (vs[:, g] @ strat[g]) / max(np.dot(m["vol"][g], strat[g]), 1e-12)
            new = np.clip(gw * np.exp(0.25 * tr) * np.maximum(vr, 1e-6) ** -0.5, gw - spec.tactical_limit, gw + spec.tactical_limit)
            new = np.clip(new, 0, min(1.0, gw + strat[cash]))
            d = new - gw
            if gw > 0:
                W[:, g] += (strat[g] / gw)[None, :] * d[:, None]
            W[:, cash] -= d
        W = np.maximum(W, 0)
        return W / W.sum(axis=1, keepdims=True)
    if pol == "lifecycle_adaptive":
        if "lc" not in cache:
            cache["lc"] = lifecycle_target(m, {**st, "wealth": 1e12, "human_capital": 0.0, "pv_liabilities": 0.0}, spec)
        b = blocks(elig)
        rk = sorted(b.get("growth", []) + b.get("credit", []) + b.get("real", []))
        _, _, base_notes = cache["lc"]
        out = np.zeros((N, n))
        # rebuild the per-path strategic target with the same formulas as lifecycle_target
        probe = lifecycle_target(m, {**st, "wealth": 1.0, "human_capital": 0.0, "pv_liabilities": 0.0}, spec)
        alpha = probe[2]["alpha_total_wealth"]
        mix_full = probe[0].copy()          # s = min(alpha, 1) with no human capital and no hedge
        s0 = probe[2]["risky_share"]
        mix = np.zeros(n)
        if s0 > 0:
            mix[rk] = mix_full[rk] / s0
        hedge_probe = lifecycle_target(m, {**st, "wealth": 1.0, "human_capital": 0.0, "pv_liabilities": 1e12}, spec)
        bond_w = hedge_probe[0].copy()
        bond_w[rk] = 0.0
        bond_w[cash] = 0.0
        bsum = bond_w.sum()
        if bsum > 0:
            bond_w = bond_w / bsum
        tw = np.maximum(Wn, 1.0) + st["human_capital"]
        s = np.clip(alpha * tw / np.maximum(Wn, 1.0), 0.0, 1.0)
        hedge = np.clip(st["pv_liabilities"] / np.maximum(tw, 1.0), 0.0, 1.0)
        safe = 1 - s
        out += s[:, None] * mix[None, :]
        if bsum > 0:
            out += (safe * hedge)[:, None] * bond_w[None, :]
            out[:, cash] += safe * (1 - hedge)
        else:
            out[:, cash] += safe
        g = b.get("growth", [])
        if g and spec.tactical_limit > 0:
            tr = np.sign(trend[:, g] @ mix[g] / max(mix[g].sum(), 1e-12))
            vr = (vs[:, rk] @ mix[rk]) / max(np.dot(np.sqrt(np.diag(m["cov"]))[rk], mix[rk]), 1e-12)
            d = spec.tactical_limit * (0.5 * tr - 0.5 * (vr > 1.5))
            d = np.clip(d, -s, np.minimum(out[:, cash], 1 - s))
            out += d[:, None] * mix[None, :]
            out[:, cash] -= d
        out = np.maximum(out, 0)
        return out / out.sum(axis=1, keepdims=True)
    raise ValueError(pol)


def forward(spec: HistoricalReplaySpec, h: History, cand: list[str], pol: str, rng_seed: int,
            snap: dict[str, Any], hold: NDArray[np.float64], salary: float) -> dict[str, Any]:
    """Bootstrap continuation from the exact final state (dollars of the last historical month) to the final age."""
    inv = spec.investor
    elig = snap["eligible"]
    A = len(cand)
    N = spec.forward_paths
    age0 = inv.start_age + len(h.dates) / 12.0
    months = int(round((inv.final_age - age0) * 12))
    if months <= 0 or N == 0:
        return {"available": False, "reason": "investor is past the final age or no forward paths requested"}
    D = h.dates[-1] + pd.Timedelta(days=1)
    Rk = info_returns(h, D, h.dates[-1])[elig].dropna()
    cpi = h.cpi.reindex(Rk.index)
    keep = cpi.notna().to_numpy()
    X = Rk.to_numpy()[keep]
    cp = cpi.to_numpy()[keep]
    real = (1 + X) / (1 + cp[:, None]) - 1
    rng = np.random.default_rng(rng_seed)
    Tm, bl = len(real), spec.forward_block_months
    starts = rng.integers(0, Tm - bl, size=(N, months // bl + 2))
    rows = (starts[:, :, None] + np.arange(bl)[None, None, :]).reshape(N, -1)[:, :months]
    Rf = real[rows]
    Cf = cp[rows]
    ix = [cand.index(c) for c in elig]
    Rfull = np.zeros((N, months, A))
    Rfull[:, :, ix] = Rf
    retire_m = int(round((inv.retirement_age - age0) * 12))
    hh = np.broadcast_to(hold, (N, A)).copy()
    sal = salary
    gamma = spec.preferences.gamma
    beta = spec.preferences.beta_annual ** (1 / 12)
    p_alive = surv(age0, inv.sex)
    util = np.zeros(N)
    first = np.full(N, -1)
    unmet = np.zeros(N)
    w_at_ret = None
    spend = 0.0
    alloc = []
    wealth_q = []
    trail = np.concatenate([np.broadcast_to(real[-12:], (N, 12, len(elig))), Rf], axis=1)
    m = snap
    cache: dict[str, Any] = {}
    disc_sum = 0.0
    p_hi = None
    rg = m.get("regime")
    # vectorised Hamilton filter for the regime policy (frozen boundary model, path data)
    regime_model = None
    if pol == "regime_adaptive":
        mdl = _SNAP_MODEL.get("ms")
        regime_model = mdl
        prior = np.broadcast_to(np.asarray(rg["p"]), (N, 2)).copy()
    i_eq, i_b = (elig.index("us_eq") if "us_eq" in elig else None), (elig.index("ust_10y") if "ust_10y" in elig else None)
    rp_cache = None
    lia = liabilities(inv, age0, sal, snap["real_rate"])
    for t in range(months):
        age = age0 + t / 12
        if t % 12 == 0 and t > 0:
            if age < inv.retirement_age:
                sal *= 1 + wage_growth(age - 1, inv.real_wage_growth_young)
            lia = liabilities(inv, age, sal, snap["real_rate"])
        Wn = hh.sum(axis=1)
        win12 = trail[:, t:t + 12]
        cash_e = elig.index("tbill")
        trend = np.prod(1 + win12, axis=1) - np.prod(1 + win12[:, :, cash_e], axis=1)[:, None]
        vs = win12.std(axis=1, ddof=1) * np.sqrt(12)
        st = {"age": age, "wealth": float(np.median(Wn)), "salary": sal, "years_to_retirement": max(inv.retirement_age - age, 0.0),
              "human_capital": lia["human_capital"] if age < inv.retirement_age else 0.0, "pv_liabilities": lia["pv_liabilities"],
              "liability_duration": lia["liability_duration"], "funding_ratio": 1.0}
        pv_base = None
        if pol == "vol_target":
            if rp_cache is None:
                rp_cache = target("sixty_forty", m, st, spec)["strategic"]
            pv_base = (win12 @ rp_cache).std(axis=1, ddof=1) * np.sqrt(12)
        if pol == "regime_adaptive" and regime_model is not None and i_eq is not None and i_b is not None:
            x = np.column_stack([np.log1p(Rf[:, t - 1, i_eq]) if t > 0 else np.log1p(real[-1, i_eq]) * np.ones(N),
                                 np.log1p(Rf[:, t - 1, i_b]) if t > 0 else np.log1p(real[-1, i_b]) * np.ones(N),
                                 Cf[:, t - 1] if t > 0 else cp[-1] * np.ones(N)])
            ld = _logpdf_all(x, regime_model.mu, regime_model.sigma)
            mx = ld.max(axis=1, keepdims=True)
            post = prior * np.exp(ld - mx)
            post /= post.sum(axis=1, keepdims=True)
            prior = post @ regime_model.P
            p_hi = prior[:, 1]
        elif pol == "regime_adaptive":
            p_hi = np.full(N, rg["p_high_inflation"] if rg else 0.5)
        tw = forward_targets(pol, m, spec, st, Wn, trend, vs, pv_base, p_hi, cache)
        targets = np.zeros((N, A))
        targets[:, ix] = tw
        if t >= retire_m and spend == 0.0:
            spend = lia["annual_net_spend_real"]
        yi = int(t // 12)
        df = beta ** t * (p_alive[yi] if yi < len(p_alive) else 0.0)
        disc_sum += df
        cfg = _cfg(spec, inv, 1.0, hh, t, retire_m, spend, trace=-1, cash_idx=cand.index("tbill"), disc=np.array([df]))
        cfg.sched = np.ascontiguousarray(targets.reshape(1, N, A))
        working = age < inv.retirement_age
        o = L.simulate(Rfull[:, t:t + 1], np.arange(N, dtype=np.int64)[:, None],
                       np.full((N, 1), sal / 12.0 if working else 0.0),
                       np.full((N, 1), 0.0 if working else inv.pension_ratio * lia["final_salary_real"] / 12.0), cfg)
        util += o.utility
        unmet += o.unmet
        first = np.where((first < 0) & (o.first_shortfall >= 0), t, first)
        hh = o.holdings_end
        if t == retire_m:
            w_at_ret = hh.sum(axis=1).copy()
        if t % 12 == 0:
            ws = hh / np.maximum(hh.sum(axis=1, keepdims=True), 1e-9)
            alloc.append({"age": round(age, 2), "q": {c: np.round(np.quantile(ws[:, cand.index(c)], [0.1, 0.5, 0.9]), 4).tolist() for c in elig}})
            wealth_q.append({"age": round(age, 2), "q": np.round(np.quantile(hh.sum(axis=1), [0.05, 0.25, 0.5, 0.75, 0.95]), 0).tolist()})
    ce = ce_from_utility(float(np.mean(util)), gamma, disc_sum) * 1000.0 * 12.0
    term = hh.sum(axis=1)
    return {"available": True, "paths": N, "months": months, "start_age": round(age0, 2), "retirement_month": retire_m,
            "start_wealth": float(hold.sum()), "start_holdings": dict(zip(cand, np.round(hold, 2).tolist())),
            "ce_consumption": float(ce), "p_no_shortfall": float((first < 0).mean()),
            "unmet_mean": float(unmet.mean()), "unmet_cvar95": S.cvar(unmet),
            "wealth_at_retirement": None if w_at_ret is None else np.round(np.quantile(w_at_ret, [0.05, 0.25, 0.5, 0.75, 0.95]), 0).tolist(),
            "terminal": np.round(np.quantile(term, [0.05, 0.5, 0.95]), 0).tolist(), "wealth_by_age": wealth_q,
            "allocation_by_age": alloc, "spend_target_real": lia["annual_net_spend_real"],
            "bootstrap_window": [str(Rk.index[0].date()), str(Rk.index[-1].date())], "block_months": bl}


_SNAP_MODEL: dict[str, Any] = {}


# ============================================================================== study entry point
def run_historical_replay(spec: HistoricalReplaySpec, progress: S.Progress) -> dict[str, Any]:
    progress("loading_history", 0.01)
    h = load_history(spec)
    pols = [p for p in spec.policies if p in POLICIES]
    base = replay(spec, h, pols, progress)
    cand = base["candidates"]
    snaps = base["snaps"]
    last = snaps[-1]
    if base["fixed_set"] is not None:
        last = restrict(last, base["fixed_set"])
    progress("forward", 0.66)
    _SNAP_MODEL["ms"] = _boundary_regime_model(spec, h)
    fwd = {}
    for k, pol in enumerate(pols):
        rp = base["policies"][pol]
        if not rp.get("available"):
            continue
        stt = rp.pop("_state")
        hold_real = stt["holdings"]          # dollars of the last historical month = real dollars at the boundary
        fwd[pol] = forward(spec, h, cand, pol, spec.seed + 13, last, hold_real, stt["salary"])
        progress("forward %s" % pol, 0.66 + 0.2 * (k + 1) / len(pols))
    for pol in pols:
        base["policies"][pol].pop("_state", None)
    exps = experiments(spec, h, progress) if spec.experiments else None
    progress("summarising", 0.97)
    market = market_series(snaps, h)
    elig_timeline = [{"date": str(s["date"].date()), "eligible": s["eligible"]} for s in snaps]
    warnings = ["model_generated: Treasury, TIPS and investment-grade returns are repriced from public yields",
                "investment-grade credit is repriced from the Moody's Aaa yield with no default or downgrade losses"]
    gaps = [str(d.date()) for d in h.dates if pd.isna(h.cpi.get(d, np.nan))]
    if gaps:
        warnings.append("CPI not published for " + ", ".join(gaps) + " (no value exists); real values treat those months as "
                        "zero measured inflation and TIPS returns are unavailable for them")
    if h.not_ingested:
        warnings.append("not ingested (WRDS-only, never proxied): " + ", ".join(h.not_ingested))
    if base["dropped"]:
        warnings.append("fixed-universe mode: sleeves eligible only part of the window are excluded for comparability: "
                        + ", ".join(base["dropped"]) + " (use universe_mode='expanding' to admit them when eligible)")
    return {
        "dates": [str(d.date()) for d in h.dates], "candidates": cand,
        "asset_class": {c: (SERIES[c].asset_class if c in SERIES else "other") for c in cand},
        "block_of": {c: BLOCK_OF.get(SERIES[c].asset_class if c in SERIES else "other", "real") for c in cand},
        "universe_mode": spec.universe_mode, "fixed_set": base["fixed_set"], "dropped": base["dropped"],
        "not_ingested": h.not_ingested, "eligibility": elig_timeline, "policies": base["policies"],
        "forward": fwd, "market": market, "events": [{"date": d, "label": lab} for d, lab in EVENTS
                                                      if h.dates[0] <= pd.Timestamp(d + "-01") <= h.dates[-1]],
        "reasons": L.REASONS, "investor": spec.investor.model_dump(), "experiments": exps, "warnings": warnings,
        "timing": {"decision": "first day of month t", "returns_known_through": "month t-1",
                   "cpi_known_through": "month t-2 (15-day publication lag)", "yields_known_through": "month t-1",
                   "order": "flows -> fund flows toward target -> rebalancing decision -> trades + costs -> earn month-t returns"},
        "definitions": {"real": "real values deflate by realised CPI into dollars of " + str(h.dates[-1].date()),
                        "forward": "bootstrap of joint real returns of the eligible sleeves (and CPI) over the information set at the last historical month; policies recompute targets on every path every month; dollars of the last historical month"},
    }


def _boundary_regime_model(spec: HistoricalReplaySpec, h: History) -> MarkovSwitching | None:
    """The regime model as last refitted inside the replay (information set of the last historical month)."""
    mm = MarketModel(spec, h)
    mm.ms_months = spec.refit_months
    try:
        mm.snapshot(len(h.dates) - 1)
    except Exception:
        return None
    return mm.ms


def market_series(snaps: list[dict[str, Any]], h: History) -> dict[str, Any]:
    g = lambda k: [s["states"].get(k) for s in snaps]  # noqa: E731
    return {"y_tb3ms": g("y_tb3ms"), "y_dgs10": g("y_dgs10"), "y_dgs30": g("y_dgs30"), "y_dfii10": g("y_dfii10"),
            "credit_spread": [(s["states"].get("y_baa") - s["states"].get("y_aaa")) if s["states"].get("y_baa") is not None else None for s in snaps],
            "vix": g("s_vixcls"), "infl12": [s["infl12"] for s in snaps], "real_rate": [s["real_rate"] for s in snaps],
            "corr_eq_bond_36m": [s["corr_eq_bond_36m"] for s in snaps],
            "p_high_inflation": [s["regime"]["p_high_inflation"] if s["regime"] else None for s in snaps],
            "regime_fit_end": [s["regime"]["fit_end"] if s["regime"] else None for s in snaps],
            "info_last_return": [s["info_last_return"] for s in snaps], "info_last_cpi": [s["info_last_cpi"] for s in snaps],
            "window": [s["window"] for s in snaps],
            "vol": [dict(zip(s["eligible"], np.round(s["vol"], 4).tolist())) for s in snaps],
            "vol_short": [dict(zip(s["eligible"], np.round(s["vol_short"], 4).tolist())) for s in snaps],
            "trend": [dict(zip(s["eligible"], np.round(s["trend"], 4).tolist())) for s in snaps],
            "mu_ex": [dict(zip(s["eligible"], np.round(s["mu_ex"], 4).tolist())) for s in snaps]}


EXP_POLICIES = ["sixty_forty", "target_date", "vol_target", "pp_multi_asset", "lifecycle_adaptive"]


def experiments(spec: HistoricalReplaySpec, h: History, progress) -> dict[str, Any]:
    """Cohorts, walk-forward start years, estimation windows and lifecycle ablations (realised outcomes)."""
    out: dict[str, Any] = {"cohorts": [], "start_years": [], "windows": [], "ablations": []}

    def row(sp, pols, ablation=None):
        hh = load_history(sp)
        res = replay(sp, hh, pols, None, detail=False, ablation=ablation)
        return {p: {k: v for k, v in res["policies"][p].items() if k not in ("_state",)} for p in pols}

    for age, w0, sal in ((20, 10_000, 45_000), (40, 150_000, 80_000), (60, 600_000, 100_000)):
        sp = spec.model_copy(update={"investor": spec.investor.model_copy(update={"start_age": float(age), "initial_wealth": float(w0), "salary": float(sal)}),
                                     "experiments": False})
        out["cohorts"].append({"start_age": age, "initial_wealth": w0, "salary": sal, "results": row(sp, EXP_POLICIES)})
    progress("experiments: cohorts", 0.9)
    for y in ("1996-01", "2001-01", "2007-01", "2012-01"):
        sp = spec.model_copy(update={"start": y, "experiments": False})
        try:
            out["start_years"].append({"start": y, "results": row(sp, EXP_POLICIES)})
        except Exception as exc:  # reported, never hidden
            out["start_years"].append({"start": y, "error": str(exc)[:200]})
    for wnd in (60, 120, None):
        sp = spec.model_copy(update={"estimation_window_months": wnd, "experiments": False})
        out["windows"].append({"window_months": wnd if wnd else "expanding", "results": row(sp, ["regime_adaptive", "crra_parametric", "lifecycle_adaptive"])})
    progress("experiments: windows", 0.94)
    sp = spec.model_copy(update={"experiments": False})
    for ab in (None, "no_human_capital", "no_liability_hedge", "no_market_signals", "frozen_target", "no_rebalancing"):
        r = row(sp, ["lifecycle_adaptive"], ablation=ab)["lifecycle_adaptive"]
        out["ablations"].append({"ablation": ab or "full", **r})
    return out
