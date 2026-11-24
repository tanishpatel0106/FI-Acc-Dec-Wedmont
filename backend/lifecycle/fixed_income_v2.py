"""Page F additions: key-rate durations, Taylor vs full repricing, twist grid, real liability gap,
cash-flow matching ladder, stock-bond co-loss and credit views. Derived statistics only."""
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from lifecycle.data import panel
from lifecycle.engine import dependence, fixed_income

KEYS = (2.0, 5.0, 10.0, 20.0, 30.0)


def _curve(kind: str, date: str | None):
    ids = ["gsw_nom_%02d" % m for m in range(1, 31)] if kind == "nominal" else ["gsw_real_%02d" % m for m in range(2, 21)]
    w = panel.wide(ids).dropna()
    if date is not None:
        w = w[w.index <= pd.Timestamp(date) + pd.offsets.MonthEnd(0)]
    row = w.iloc[-1]
    return w.index[-1].date().isoformat(), np.array([int(c[-2:]) for c in row.index], float), row.to_numpy()


def _key_bump(m: np.ndarray, key: float, bp: float = 1.0) -> np.ndarray:
    """Triangular key-rate shift: 1bp at the key tenor, linearly to 0 at the neighbouring keys (sums to parallel)."""
    k = list(KEYS)
    i = k.index(key)
    lo = k[i - 1] if i > 0 else 0.0
    hi = k[i + 1] if i < len(k) - 1 else 1e9
    s = np.zeros_like(m)
    for j, x in enumerate(m):
        if i == 0 and x <= key:
            s[j] = 1.0
        elif i == len(k) - 1 and x >= key:
            s[j] = 1.0
        elif lo <= x <= key:
            s[j] = (x - lo) / (key - lo)
        elif key < x <= hi:
            s[j] = (hi - x) / (hi - key)
    return s * bp / 1e4


def _pv_flows(times, flows, m, z, shift=None):
    zz = np.interp(times, m, z + (0 if shift is None else shift))
    return float(np.sum(flows * np.exp(-zz * times)))


def key_rate_table(date: str | None, withdrawal: float = 40_000.0, years: int = 30) -> dict[str, Any]:
    return _krd(date, withdrawal, years, panel.catalog_hash())


@lru_cache(maxsize=16)
def _krd(date, withdrawal, years, ck) -> dict[str, Any]:
    d, m, z = _curve("nominal", date)
    par = fixed_income.zero_to_par(z, m)
    rows = []
    for mat in (2.0, 5.0, 10.0, 30.0):
        y = par[mat]
        t, f = fixed_income.cashflows(y, mat)
        p0 = _pv_flows(t, f, m, z)
        krd = {}
        for k in KEYS:
            p1 = _pv_flows(t, f, m, z, _key_bump(m, k))
            krd[str(int(k))] = float(-(p1 - p0) / p0 / 1e-4)
        par_shift = float(-(_pv_flows(t, f, m, z, np.full_like(m, 1e-4)) - p0) / p0 / 1e-4)
        rows.append({"instrument": "Treasury %gY par bond" % mat, "maturity": mat, "yield": y, "krd": krd,
                     "sum_krd": float(sum(krd.values())), "parallel_effective_duration": par_shift,
                     "modified_duration": fixed_income.modified_duration(y, y, mat),
                     "convexity": fixed_income.convexity(y, y, mat), "dv01_per_1m": fixed_income.dv01(y, y, mat) * 1e6 / 100})
    # liability: level real withdrawals discounted on the nominal curve as a duration proxy (nominal KRDs)
    times = np.arange(1, years + 1, dtype=float)
    flows = np.full(years, withdrawal)
    l0 = _pv_flows(times, flows, m, z)
    lk = {str(int(k)): float(-(_pv_flows(times, flows, m, z, _key_bump(m, k)) - l0) / l0 / 1e-4) for k in KEYS}
    portfolio = {"weights": {"2": 0.1, "5": 0.2, "10": 0.4, "30": 0.3}}
    pk = {str(int(k)): sum(portfolio["weights"][str(int(r["maturity"]))] * r["krd"][str(int(k))] for r in rows) for k in KEYS}
    return {"date": d, "keys": [int(k) for k in KEYS], "rows": rows, "liability": {"pv": l0, "krd": lk,
            "definition": "%d years of $%.0f level withdrawals, nominal zero curve" % (years, withdrawal)},
            "portfolio": {**portfolio, "krd": pk, "gap_vs_liability": {k: pk[k] - lk[k] for k in pk}},
            "check": "triangular key-rate bumps sum to a parallel 1bp shift; sum_krd ~ effective duration"}


def twist_grid(date: str | None) -> dict[str, Any]:
    d, m, z = _curve("nominal", date)
    try:
        rd, rm, rz = _curve("real", date)
    except Exception:
        rm = rz = None
    moves = [-100, -50, 0, 50, 100]
    par = fixed_income.zero_to_par(z, m)
    y10 = par[10.0]
    p0 = fixed_income.price_on_curve(y10, 10.0, m, z)
    nom = [[fixed_income.price_on_curve(y10, 10.0, m, z, fixed_income.twist(m, s, lg)) / p0 - 1 for lg in moves]
           for s in moves]
    tips = None
    if rm is not None:
        rpar = fixed_income.zero_to_par(rz, rm)
        y = rpar.get(10.0, float(np.interp(10, rm, rz)))
        r0 = fixed_income.price_on_curve(y, 10.0, rm, rz)
        tips = [[fixed_income.price_on_curve(y, 10.0, rm, rz, fixed_income.twist(rm, s, lg)) / r0 - 1 for lg in moves]
                for s in moves]
    return {"date": d, "short_moves_bp": moves, "long_moves_bp": moves, "nominal_10y": nom, "tips_10y_real": tips,
            "pivot": "5y", "labels": {"bear_steepener": "short 0 / long +", "bull_flattener": "short 0 / long -"}}


def liability_gap(date: str | None, withdrawal: float, years: int, pension: float, mortality: bool,
                  inflation_shift_bp: float) -> dict[str, Any]:
    rd, rm, rz = _curve("real", date)
    from lifecycle.data.ingest_ssa import load_life_table
    from lifecycle.engine.lifecycle import mortality as M

    q = M.q_vector(load_life_table(), "unisex")
    S = M.monthly_survival(q, 65.0, years * 12, mortality)[::12][1:]
    times = np.arange(1, years + 1, dtype=float)
    flows = np.maximum(withdrawal - pension, 0.0) * S
    base = fixed_income.liability_pv_duration(flows, times, rm, rz)
    sens = {}
    for lab, kw in (("no mortality", dict(mortality=False)), ("pension +$10k", dict(pension=pension + 10_000)),
                    ("real rates -100bp", dict(shift=-0.01)), ("real rates +100bp", dict(shift=0.01))):
        Sx = M.monthly_survival(q, 65.0, years * 12, kw.get("mortality", mortality))[::12][1:]
        fl = np.maximum(withdrawal - kw.get("pension", pension), 0.0) * Sx
        r = fixed_income.liability_pv_duration(fl, times, rm, rz + kw.get("shift", 0.0))
        sens[lab] = r
    # inflation: if spending is real but assets nominal, an extra inflation drift raises nominal liabilities
    infl_mult = (1 + inflation_shift_bp / 1e4) ** times
    sens["inflation +%gbp/yr (nominal funding)" % inflation_shift_bp] = fixed_income.liability_pv_duration(
        flows * infl_mult, times, rm, rz)
    return {"date": rd, "pv": base["pv"], "duration": base["duration"], "sensitivities": sens,
            "funding_ratio_for_1m": 1e6 / base["pv"] if base["pv"] > 0 else None,
            "flows": flows.tolist(), "times": times.tolist(), "curve": "GSW TIPS real zero (flat beyond 20y)"}


def ladder(date: str | None, withdrawal: float, years: int, budget: float) -> dict[str, Any]:
    """Cash-flow matching with real zero-coupon (TIPS-strip-like) bonds priced on the real curve."""
    rd, rm, rz = _curve("real", date)
    times = np.arange(1, years + 1, dtype=float)
    price = np.exp(-np.interp(times, rm, rz) * times)
    cost = withdrawal * price
    cum = np.cumsum(cost)
    funded = cum <= budget
    return {"date": rd, "years": times.tolist(), "price_per_dollar": price.tolist(), "cost": cost.tolist(),
            "cumulative_cost": cum.tolist(), "funded": funded.tolist(), "budget": budget,
            "funded_years": int(funded.sum()), "unfunded_years": [int(t) for t, f in zip(times, funded) if not f],
            "note": "monthly spending aggregated to annual maturities; real zero beyond 20y held flat; "
                    "illustrative pricing (not executable quotes)"}


def coloss_panel() -> dict[str, Any]:
    return _coloss(panel.catalog_hash())


@lru_cache(maxsize=4)
def _coloss(ck) -> dict[str, Any]:
    u = panel.universe_data("core_long_history")
    x = u.nominal["us_eq"].to_numpy()
    y = u.nominal["ust_10y"].to_numpy()
    w = 60
    co, corr = [], []
    for t in range(len(x)):
        if t < w:
            co.append(None)
            corr.append(None)
            continue
        xs, ys = x[t - w:t], y[t - w:t]
        worst = xs <= np.quantile(xs, 0.2)
        co.append(float(np.mean(ys[worst] < 0)))
        corr.append(float(np.corrcoef(xs, ys)[0, 1]))
    arr = np.array([np.nan if v is None else v for v in co])
    med = np.nanmedian(arr)
    hi = arr > med
    # consequence for shortfall: 60/40 4% success on bootstraps of high vs low co-loss months
    from lifecycle.engine.scenarios.base import generate
    from lifecycle.engine.scenarios.bootstrap import StationaryBootstrap

    res = {}
    real = u.real_array()
    infl = u.inflation.to_numpy()
    wv = np.array([0.6 if a == "us_eq" else (0.4 if a == "ust_10y" else 0.0) for a in u.assets])
    for lab, mask in (("high co-loss months", hi), ("low co-loss months", (~hi) & np.isfinite(arr))):
        if mask.sum() < 60:
            continue
        m = StationaryBootstrap(real[mask], infl[mask])
        ten = generate(m, u.assets, 1000, 360, 9, None)
        R = ten.real_returns @ wv
        W = np.ones(1000)
        fail = np.zeros(1000, bool)
        for t in range(360):
            W = W - 0.04 / 12
            fail |= W <= 0
            W = np.maximum(W, 0) * (1 + R[:, t])
        res[lab] = {"p_success_30y_4pct_6040": float(1 - fail.mean()), "n_months": int(mask.sum())}
    return {"dates": [d.date().isoformat() for d in u.real.index], "coloss_freq_60m": co, "corr_60m": corr,
            "definition": "share of months with a negative Treasury return among the worst 20% equity months in "
                          "the trailing 60 months", "shortfall_consequence": res,
            "caveat": "conditioning on ex-post co-loss classification is descriptive (not a tradable signal)"}


def credit_surface() -> dict[str, Any]:
    cat = panel.catalog()
    have = {s: str(cat[cat["series_id"] == s]["source"].iloc[0]) for s in ("ig_credit", "hy_credit")
            if (cat["series_id"] == s).any()}
    wrds_bonds = any(v.startswith("wrds:") for v in have.values())
    out: dict[str, Any] = {"bond_level_available": False,
                           "reason": "bond-level WRDS Bond Returns / TRACE / FISD entitlement not ingested; "
                                     "credit quality x duration surface requires security-level data",
                           "index_sleeves": have, "selection_bias": "index-level sleeves only: survivorship, "
                                                                     "liquidity and rating-migration effects not "
                                                                     "modelled"}
    if not wrds_bonds:
        out["note"] = "ig_credit is model_generated from Moody's Aaa yields (public); hy_credit unavailable"
    rows = []
    for s, src in have.items():
        u = panel.universe_data("modern") if s in panel.universe_data("modern").assets else None
        if u is None:
            continue
        r = u.real[s]
        rows.append({"series": s, "source": src, "real_mean": float(r.mean() * 12), "real_vol": float(r.std() * np.sqrt(12)),
                     "worst_12m": float(((1 + r).rolling(12).apply(np.prod, raw=True) - 1).min()),
                     "corr_equity": float(np.corrcoef(r, u.real["us_eq"])[0, 1])})
    out["index_stats"] = rows
    return out


def spreads_history() -> dict[str, Any]:
    w = panel.wide(["y_baa", "y_aaa", "y_dgs10"]).dropna()
    return {"dates": [d.date().isoformat() for d in w.index], "baa_aaa": (w["y_baa"] - w["y_aaa"]).round(5).tolist(),
            "baa_t10": (w["y_baa"] - w["y_dgs10"]).round(5).tolist(),
            "terms": "FRED Moody's series (public, terms of use apply); not imputed as corporate bond total returns",
            "retention": "full public history; ICE BofA OAS excluded (3-year public retention since 2026)"}


def full_vs_taylor(date: str | None) -> dict[str, Any]:
    d, m, z = _curve("nominal", date)
    rows = fixed_income.shock_table(m, z, [2.0, 5.0, 10.0, 30.0], [-300, -200, -100, -50, -25, 25, 50, 100, 200, 300])
    return {"date": d, "rows": rows}


def dependence_quick() -> dict[str, Any]:
    u = panel.universe_data("core_long_history")
    return {"joint_loss": dependence.joint_loss_frequency(u.nominal["us_eq"].to_numpy(), u.nominal["ust_10y"].to_numpy())}
