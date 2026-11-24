"""Multi-asset Permanent Portfolio and dynamic asset allocation across asset classes.

Asset classes are grouped into building blocks by their catalog class: growth (equity), duration (Treasuries,
TIPS), credit (IG, HY), real & currency (gold, commodities, currencies) and cash. Within a block the sleeves
are risk-balanced with calibration-window volatilities (train-only information).

Policy families (all long-only, no leverage, evaluated with the holdings ledger on common random numbers):
  static   - 60/40 benchmark, equal weight, multi-asset Permanent Portfolio (25% growth / duration / real /
             cash), static risk parity (equal risk contribution, calibration covariance)
  regime   - building-block weights per point-in-time regime (filtered, lagged), fitted on training paths
  trend    - time-series momentum: a risky sleeve whose trailing 12-month excess return over T-bills is
             negative is moved to cash (signal uses returns through t-1)
  risk     - inverse trailing volatility (monthly) and volatility targeting (risk-parity mix scaled to a target
             annual volatility, remainder in cash, never above 100% invested)
  utility  - CRRA-optimal static block mix and a parametric policy (trend and volatility tilts of that mix),
             both fitted on training paths (seed set A) and scored on disjoint test paths (seed set B)

Dynamic policies give every path its own target-weight schedule (ledger state index = path). Signals at the
start of the simulation use the last 12 observed months of the calibration window (common to all paths).
The result is model-conditional research output, not advice.
"""
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pydantic import Field

from lifecycle.data.series import SERIES
from lifecycle.studies import common as S

BLOCK_OF = {"equity": "growth", "rates": "duration", "credit": "credit", "currency": "real", "commodities": "real",
            "real_assets": "real", "cash": "cash"}
BLOCKS = ("growth", "duration", "credit", "real", "cash")
FAMILY = {"sixty_forty": "static", "equal_weight": "static", "pp_multi_asset": "static", "risk_parity": "static",
          "regime_blocks": "regime", "trend_tsmom": "trend", "inverse_vol": "risk", "vol_target": "risk",
          "crra_static": "utility", "crra_parametric": "utility"}
LABELS = {
    "sixty_forty": "60/40 (US equity / 10Y Treasury)", "equal_weight": "Equal weight, all sleeves",
    "pp_multi_asset": "Multi-asset Permanent Portfolio (growth / duration / real & currency / cash)",
    "risk_parity": "Static risk parity (equal risk contribution)", "regime_blocks": "Regime-based block allocation",
    "trend_tsmom": "Trend (12-month time-series momentum to cash)", "inverse_vol": "Inverse trailing volatility",
    "vol_target": "Volatility target on the risk-parity mix", "crra_static": "CRRA-optimal static block mix",
    "crra_parametric": "CRRA parametric (trend & volatility tilts)",
}


class MultiAssetSpec(S.Frozen):
    data: S.StudyData = Field(default_factory=lambda: S.StudyData(universe="multi_asset_public"))
    scenario: S.StudyScenario = Field(default_factory=lambda: S.StudyScenario(generator="markov_switching",
                                                                              n_paths=2000, n_train_paths=1000))
    investor: S.StudyInvestor = Field(default_factory=lambda: S.StudyInvestor(horizon_years=30))
    preferences: S.StudyPrefs = Field(default_factory=S.StudyPrefs)
    costs: S.StudyCosts = Field(default_factory=lambda: S.StudyCosts(commission_bps=1, half_spread_bps=2))
    policies: tuple[str, ...] = tuple(FAMILY)
    benchmark: str = "sixty_forty"
    withdrawal: float = Field(0.04, ge=0, le=0.15)
    saver_start_age: float = Field(35.0, ge=20, le=60)
    saver_income: float = Field(100_000.0, ge=0)
    saver_savings_rate: float = Field(0.15, ge=0, le=0.8)
    block_step: float = Field(0.25, gt=0, le=0.5)
    trend_months: int = Field(12, ge=3, le=24)
    vol_months: int = Field(12, ge=6, le=36)
    target_vol: float = Field(0.08, gt=0.01, le=0.3)
    robustness_generators: tuple[str, ...] = ("bootstrap",)
    label: str | None = None


# ----------------------------------------------------------------------------------------- building blocks
def asset_class(a: str) -> str:
    s = SERIES.get(a)
    return s.asset_class if s else "other"


def blocks_of(assets: tuple[str, ...]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {b: [] for b in BLOCKS}
    for i, a in enumerate(assets):
        out[BLOCK_OF.get(asset_class(a), "real")].append(i)
    return {b: v for b, v in out.items() if v}


def within_block(assets: tuple[str, ...], vol: NDArray[np.float64]) -> dict[str, NDArray[np.float64]]:
    """Inverse-volatility weights inside each block (sums to one per block)."""
    out = {}
    for b, idx in blocks_of(assets).items():
        v = np.zeros(len(assets))
        iv = 1.0 / np.maximum(vol[idx], 1e-6)
        v[idx] = iv / iv.sum()
        out[b] = v
    return out


def block_mix(mix: dict[str, float], wb: dict[str, NDArray[np.float64]]) -> NDArray[np.float64]:
    w = sum(mix.get(b, 0.0) * wb[b] for b in wb)
    w = np.asarray(w, dtype=float)
    return w / w.sum()


def simplex(names: list[str], step: float) -> list[dict[str, float]]:
    n = int(round(1 / step))
    out: list[dict[str, float]] = []

    def rec(i: int, left: int, cur: list[int]) -> None:
        if i == len(names) - 1:
            out.append(dict(zip(names, [c * step for c in cur + [left]])))
            return
        for k in range(left + 1):
            rec(i + 1, left - k, cur + [k])
    rec(0, n, [])
    return out


def erc(cov: NDArray[np.float64], iters: int = 500) -> NDArray[np.float64]:
    """Equal-risk-contribution weights (long-only) by fixed-point iteration."""
    n = cov.shape[0]
    w = np.ones(n) / n
    for _ in range(iters):
        mrc = cov @ w
        rc = w * mrc
        target = rc.sum() / n
        w = w * (target / np.maximum(rc, 1e-18)) ** 0.5
        w = w / w.sum()
    return w


# ----------------------------------------------------------------------------------------- path signals
def trailing(R: NDArray[np.float64], prefix: NDArray[np.float64], months: int) -> tuple[NDArray, NDArray]:
    """Trailing `months` cumulative return and volatility known at the start of each month (uses t-months..t-1)."""
    N, T, A = R.shape
    H = np.concatenate([np.broadcast_to(prefix[-months:], (N, months, A)), R], axis=1)   # (N, months+T, A)
    L = np.log1p(np.maximum(H, -0.999))
    c = np.concatenate([np.zeros((N, 1, A)), np.cumsum(L, axis=1)], axis=1)
    c2 = np.concatenate([np.zeros((N, 1, A)), np.cumsum(H * H, axis=1)], axis=1)
    c1 = np.concatenate([np.zeros((N, 1, A)), np.cumsum(H, axis=1)], axis=1)
    idx = np.arange(T)
    cum = np.expm1(c[:, idx + months] - c[:, idx])
    s1 = c1[:, idx + months] - c1[:, idx]
    s2 = c2[:, idx + months] - c2[:, idx]
    var = np.maximum(s2 / months - (s1 / months) ** 2, 0.0) * months / max(months - 1, 1)
    return cum, np.sqrt(var * 12.0)


def per_path(W: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """(N, T, A) weights -> ledger schedule (T, N, A) and state matrix state[j, t] = j."""
    N, T, _ = W.shape
    W = W / W.sum(axis=2, keepdims=True)
    return np.ascontiguousarray(W.transpose(1, 0, 2)), np.ascontiguousarray(np.broadcast_to(np.arange(N)[:, None], (N, T)))


# ----------------------------------------------------------------------------------------- the study
def run_multi_asset(spec: MultiAssetSpec, progress: S.Progress) -> dict[str, Any]:
    u = S.universe_or_raise(spec.data)
    progress("generating_scenarios", 0.02)
    es, ctx, train = S.train_test(spec.data, spec.scenario, spec.investor, spec.preferences)
    ten = ctx.tensor
    assets = ten.assets
    T = ten.n_months
    A = len(assets)
    gamma = spec.preferences.gamma
    uf = spec.preferences.util_floor_annual
    cash = assets.index("tbill") if "tbill" in assets else None
    if cash is None:
        raise S.IncompatibleUniverse("the multi-asset study needs a T-bill (cash) sleeve")
    real = u.real[list(assets)].to_numpy()
    cov = S.hist_cov(u, assets)
    vol = np.sqrt(np.diag(cov) * 12.0)
    wb = within_block(assets, vol)
    bnames = list(wb)
    risky = [i for i in range(A) if i != cash]
    prefix = real[-max(spec.trend_months, spec.vol_months):]
    unavailable: dict[str, str] = {}

    def static(w: NDArray[np.float64], months: int | None = None) -> NDArray[np.float64]:
        return np.broadcast_to(w / w.sum(), (months or T, 1, A)).copy()

    def ev(c, sched, strat="calendar_12m", state=None, record=False, rate=None, tensor=None, spend="fixed_real"):
        return S.run(c, sched, S.strategy(strat, spec.costs), rate=spec.withdrawal if rate is None else rate,
                     record=record, cov=cov, util_floor=uf, state=state, tensor=tensor, spend=spend)

    # ---- static designs ------------------------------------------------------------------------------
    w_6040 = S.weights_vector({"us_eq": 0.6, "ust_10y": 0.4}, assets)
    w_eq = np.ones(A) / A
    pp_mix = {b: 0.25 for b in ("growth", "duration", "real", "cash") if b in wb}
    w_pp = block_mix(pp_mix, wb)
    w_rp = np.zeros(A)
    w_rp[risky] = erc(cov[np.ix_(risky, risky)])

    def dyn_weights(R: NDArray[np.float64], kind: str, base: NDArray[np.float64], theta=(0.0, 0.0)) -> NDArray[np.float64]:
        N, T = R.shape[0], R.shape[1]
        cum, tvol = trailing(R, prefix, spec.trend_months)
        _, vv = trailing(R, prefix, spec.vol_months)
        W = np.broadcast_to(base, (N, T, A)).copy()
        if kind == "trend_tsmom":
            excess = cum - cum[:, :, [cash]]
            off = excess < 0
            off[:, :, cash] = False
            moved = (W * off).sum(axis=2)
            W[off] = 0.0
            W[:, :, cash] += moved
        elif kind == "inverse_vol":
            iv = np.zeros_like(vv)
            iv[:, :, risky] = 1.0 / np.maximum(vv[:, :, risky], 1e-4)
            W = iv / iv.sum(axis=2, keepdims=True)
        elif kind == "vol_target":
            rp = (R * base).sum(axis=2)
            pre = np.broadcast_to(prefix[-spec.vol_months:] @ base, (N, spec.vol_months))
            _, pv = trailing(np.concatenate([pre, rp], axis=1)[:, spec.vol_months:, None],
                             (prefix[-spec.vol_months:] @ base)[:, None], spec.vol_months)
            scale = np.minimum(1.0, spec.target_vol / np.maximum(pv[:, :, 0], 1e-4))
            W = W * scale[:, :, None]
            W[:, :, cash] += 1.0 - scale
        elif kind == "crra_parametric":
            th_t, th_v = theta
            g = list(np.nonzero(wb["growth"])[0]) if "growth" in wb else []
            if g:
                gtrend = np.sign((cum[:, :, g] * base[g]).sum(axis=2) / max(base[g].sum(), 1e-12))
                gvol = (vv[:, :, g] * base[g]).sum(axis=2) / max(base[g].sum(), 1e-12)
                ref = float((vol[g] * base[g]).sum() / max(base[g].sum(), 1e-12))
                tilt = np.exp(th_t * gtrend) * (ref / np.maximum(gvol, 1e-4)) ** th_v
                gw = base[g][None, None, :] * np.minimum(tilt[:, :, None], 1.0 / max(base[g].sum(), 1e-12))
                delta = gw.sum(axis=2) - base[g].sum()
                W[:, :, g] = gw
                W[:, :, cash] -= delta
                neg = W[:, :, cash] < 0
                if neg.any():  # cannot borrow cash: scale the non-growth sleeves down instead
                    W[neg] = np.maximum(W[neg], 0.0)
        W = np.maximum(W, 0.0)
        return W / W.sum(axis=2, keepdims=True)

    def schedule_for(name: str, c, fitted: dict[str, Any]):
        R = c.tensor.real_returns
        Tm = c.tensor.n_months
        if name == "sixty_forty":
            return static(w_6040, Tm), None, "calendar_12m"
        if name == "equal_weight":
            return static(w_eq, Tm), None, "calendar_12m"
        if name == "pp_multi_asset":
            return static(w_pp, Tm), None, "calendar_12m"
        if name == "risk_parity":
            return static(w_rp, Tm), None, "calendar_12m"
        if name == "crra_static":
            return static(fitted["crra_static"], Tm), None, "calendar_12m"
        if name == "regime_blocks":
            per = fitted["regime_blocks"]
            return np.broadcast_to(per, (Tm, per.shape[0], A)).copy(), None, "calendar_1m"
        base = {"trend_tsmom": w_rp, "inverse_vol": w_rp, "vol_target": w_rp, "crra_parametric": fitted.get("crra_static")}[name]
        sched, state = per_path(dyn_weights(R, name, base, fitted.get("theta", (0.0, 0.0))))
        return sched, state, "calendar_1m"

    # ---- fitting on training paths (seed set A) ------------------------------------------------------
    progress("fitting", 0.08)
    grid = simplex(bnames, spec.block_step)
    fitted: dict[str, Any] = {}
    fit_info: dict[str, Any] = {"grid_size": len(grid), "blocks": bnames}
    if "crra_static" in spec.policies or "crra_parametric" in spec.policies:
        best = None
        for m in grid:
            w = block_mix(m, wb)
            ce = S.ce_of(ev(train, static(w)), gamma)
            if best is None or ce > best[0]:
                best = (ce, m, w)
        fitted["crra_static"] = best[2]
        fit_info["crra_static_blocks"] = best[1]
    if "crra_parametric" in spec.policies:
        best = None
        for th in [(a, b) for a in (0.0, 0.25, 0.5, 1.0) for b in (0.0, 0.5, 1.0)]:
            sched, state = per_path(dyn_weights(train.tensor.real_returns, "crra_parametric", fitted["crra_static"], th))
            ce = S.ce_of(ev(train, sched, "calendar_1m", state), gamma)
            if best is None or ce > best[0]:
                best = (ce, th)
        fitted["theta"] = best[1]
        fit_info["theta"] = {"trend": best[1][0], "volatility": best[1][1]}
    if "regime_blocks" in spec.policies:
        K = ten.n_regimes
        if K <= 1:
            unavailable["regime_blocks"] = "needs a regime-bearing generator (markov_switching with k_regimes > 1)"
        else:
            per = np.array([w_pp for _ in range(K)])
            choice = {}
            for k in range(K):  # coordinate search over the block simplex, one regime at a time
                best = None
                for m in grid:
                    trial = per.copy()
                    trial[k] = block_mix(m, wb)
                    sched = np.broadcast_to(trial, (T, K, A)).copy()
                    ce = S.ce_of(ev(train, sched, "calendar_1m"), gamma)
                    if best is None or ce > best[0]:
                        best = (ce, m, trial[k].copy())
                per[k] = best[2]
                choice[str(k)] = best[1]
            fitted["regime_blocks"] = per
            fit_info["regime_blocks"] = {"per_regime_blocks": choice, "signal": ten.meta.get("decision_signal"),
                                         "per_regime_weights": {str(k): dict(zip(assets, np.round(per[k], 4).tolist()))
                                                                for k in range(K)}}

    # ---- evaluation on test paths (seed set B): retiree ---------------------------------------------
    progress("simulating_retiree", 0.4)
    names = [n for n in spec.policies if n in FAMILY and n not in unavailable]
    for n in spec.policies:
        if n not in FAMILY:
            unavailable[n] = "unknown policy"
    if spec.benchmark not in names:
        raise ValueError("benchmark %s must be one of the evaluated policies" % spec.benchmark)
    outs: dict[str, Any] = {}
    strat_of: dict[str, str] = {}
    for n in names:
        sched, state, strat = schedule_for(n, ctx, fitted)
        outs[n] = ev(ctx, sched, strat, state, record=True)
        strat_of[n] = strat
    bo = outs[spec.benchmark]
    H = spec.investor.horizon_years
    iid = ten.meta.get("generator") != "historical"
    years = list(range(min(H, T // 12)))

    def mix_by_year(o) -> list[list[float]]:
        return S.to_list(o.weights_y.mean(axis=0)[: len(years)], 4) if o.weights_y.size else []

    score = []
    for n in names:
        o = outs[n]
        succ = S.success(o.first_shortfall, H * 12)
        row = {"policy": n, "label": LABELS[n], "family": FAMILY[n], "rebalancing": strat_of[n],
               "ce": S.ce_of(o, gamma), "success": float(succ.mean()), "success_ci": S.wilson(float(succ.mean()), len(succ)),
               "unmet_cvar95": S.cvar(o.unmet), "mdd_median": float(np.median(o.max_drawdown)),
               "turnover_yr": float(np.mean(o.turnover) / max(H, 1)), "cost_bps_yr": float(np.mean(o.cost) / max(np.mean(o.terminal + o.funded), 1) * 1e4 / max(H, 1)),
               "terminal_median": float(np.median(o.terminal))}
        if n != spec.benchmark:
            row["delta_ce"] = S.delta_block(o, bo, gamma)
            row["delta_success"] = S.paired_success_diff(succ, S.success(bo.first_shortfall, H * 12))
        score.append(row)

    by_regime = None
    if ten.n_regimes > 1:
        start = ten.decision_regime()[:, 1]   # regime signal available when the first decision is updated
        by_regime = []
        for k in range(ten.n_regimes):
            m = start == k
            if m.sum() < 30:
                by_regime.append({"regime": k, "n": int(m.sum()), "note": "fewer than 30 paths start here"})
                continue
            row: dict[str, Any] = {"regime": k, "n": int(m.sum())}
            for n in names:
                if n == spec.benchmark:
                    continue
                d, se = S.paired_delta_ce(outs[n].utility[m], bo.utility[m], gamma, bo.sum_disc)
                row[n] = {"delta": float(d), "lo": float(d - 1.96 * se), "hi": float(d + 1.96 * se)}
            by_regime.append(row)

    # ---- saver (accumulation with contributions): CE of total real resources at the horizon -------------
    progress("simulating_saver", 0.65)
    saver_inv = spec.investor.model_copy(update={"age": spec.saver_start_age, "retirement_age": min(spec.saver_start_age + H, 80.0),
                                                 "income": spec.saver_income, "savings_rate": spec.saver_savings_rate})
    es_s = S.experiment_spec(spec.data, spec.scenario, saver_inv, spec.preferences)
    ten_s = S.get_tensor(es_s)
    ctx_s = S.get_context(es_s, ten_s, es_s.scenario.seed)
    saver = []
    souts = {}
    for n in names:
        sched, state, strat = schedule_for(n, ctx_s, fitted)
        souts[n] = ev(ctx_s, sched, strat, state, spend="fixed_real")
    sb = souts[spec.benchmark]
    rng = np.random.default_rng(11)
    for n in names:
        o = souts[n]
        ce = S.resources_ce(o.terminal, o.funded, gamma)
        row = {"policy": n, "ce_resources": ce, "terminal_median": float(np.median(o.terminal)),
               "terminal_p05": float(np.quantile(o.terminal, 0.05)), "contributions_mean": float(np.mean(o.contributions))}
        if n != spec.benchmark:
            base = S.resources_ce(sb.terminal, sb.funded, gamma)
            boots = []
            N = len(o.terminal)
            for _ in range(200):
                i = rng.integers(0, N, N)
                boots.append(S.resources_ce(o.terminal[i], o.funded[i], gamma) / S.resources_ce(sb.terminal[i], sb.funded[i], gamma) - 1)
            row["delta_ce"] = {"delta": ce / base - 1, "lo": float(np.quantile(boots, 0.025)), "hi": float(np.quantile(boots, 0.975))}
        saver.append(row)

    # ---- robustness: same frozen policies under other generators -------------------------------------
    progress("robustness", 0.8)
    robust = []
    for gname in spec.robustness_generators:
        try:
            es_g = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences, generator=gname)
            ten_g = S.get_tensor(es_g)
            ctx_g = S.get_context(es_g, ten_g, es_g.scenario.seed)
            og = {}
            for n in names:
                if n == "regime_blocks" and ten_g.n_regimes <= 1:
                    continue
                sched, state, strat = schedule_for(n, ctx_g, fitted)
                og[n] = ev(ctx_g, sched, strat, state)
            for n, o in og.items():
                if n == spec.benchmark:
                    continue
                d = S.delta_block(o, og[spec.benchmark], gamma, n_boot=100)
                robust.append({"generator": gname, "policy": n, "delta": d["delta"], "lo": d["lo"], "hi": d["hi"]})
        except Exception as exc:  # reported, never silently dropped
            robust.append({"generator": gname, "error": str(exc)[:200]})

    progress("summarising", 0.95)
    warnings = S.common_warnings(u, ten)
    prov = S.provenance(assets)
    if "ig_credit" in assets and str(prov.get("ig_credit", {}).get("provenance")) == "model_generated":
        warnings.append("investment-grade credit is repriced from the Moody's Aaa yield (model-generated) with no default "
                        "or downgrade losses; allocations concentrated in credit overstate its value until observed "
                        "credit returns (WRDS) replace it")
    if spec.data.universe == "multi_asset_public":
        warnings.append("public tier: no gold, broad commodities or high-yield credit (WRDS-only); the real & currency "
                        "block is the G10 currency basket")
    return {
        "universe": S.universe_block(u), "scenario": S.scenario_block(ten), "n_paths": int(ten.n_paths),
        "assets": list(assets), "asset_class": {a: asset_class(a) for a in assets},
        "block_of": {a: BLOCK_OF.get(asset_class(a), "real") for a in assets}, "blocks": bnames,
        "calibration_vol": dict(zip(assets, np.round(vol, 4).tolist())),
        "benchmark": spec.benchmark, "withdrawal": spec.withdrawal, "horizon_years": H,
        "policies": [{"policy": n, "label": LABELS[n], "family": FAMILY[n]} for n in names],
        "unavailable": unavailable,
        "static_weights": {n: dict(zip(assets, np.round(w, 4).tolist())) for n, w in
                           [("sixty_forty", w_6040), ("equal_weight", w_eq), ("pp_multi_asset", w_pp), ("risk_parity", w_rp)]
                           + ([("crra_static", fitted["crra_static"])] if "crra_static" in fitted else [])},
        "fit": fit_info, "scorecard": score, "saver": saver, "by_regime": by_regime, "robustness": robust,
        "weights_by_year": {n: mix_by_year(outs[n]) for n in names}, "years": years,
        "iid": iid, "warnings": warnings,
        "definitions": {
            "ce": "CRRA certainty equivalent of funded real consumption (mortality-weighted), retiree from age "
                  + str(spec.investor.age) + " with a fixed real draw of " + str(spec.withdrawal),
            "saver": "CRRA certainty equivalent of total real resources (terminal wealth + funded draws): "
                     "contributions from age %g to retirement" % spec.saver_start_age + ", then the same fixed "
                     "real draw until the end of the simulated horizon",
            "signals": "trend and volatility use returns through t-1; regimes use the filtered, lagged probability"},
    }
