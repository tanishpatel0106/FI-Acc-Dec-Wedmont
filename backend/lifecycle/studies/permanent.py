"""E13-E18 / F3: Permanent Portfolio research laboratory (brief section 6).

All policies are evaluated on the *same* scenario tensor, spending rule, start wealth, horizon and cost
schedule (common random numbers). A policy that needs a sleeve the universe does not contain (e.g. gold
without an entitled observed gold series) is reported as unavailable with the reason - never filled with
a proxy or a zero-return stand-in.
"""
from itertools import combinations
from math import factorial
from typing import Any

import numpy as np
from pydantic import Field

from lifecycle.data import panel
from lifecycle.engine import fixed_income
from lifecycle.studies import common as S

SLEEVE_INFO = {
    "us_eq": ("Growth / prosperity", "equity beta, real growth"),
    "ust_30y": ("Deflation / disinflation hedge (long duration)", "nominal duration, inflation risk"),
    "gold": ("Monetary / inflation sensitivity", "real-rate and dollar sensitivity, no cash flows"),
    "tbill": ("Liquidity / tight-money stability", "real erosion in inflation, negligible duration"),
}
POLICY_LABELS = {
    "sixty_forty": "60/40 (US equity / 10Y Treasury)", "pp_classic": "Classic PP (Browne 15/35, annual review)",
    "pp_monthly": "PP monthly calendar", "pp_annual": "PP annual calendar",
    "pp_15_35_monthly": "PP 15/35, monthly monitoring", "pp_5pp_band": "PP 5pp band",
    "pp_intermediate": "PP, intermediate Treasury", "pp_tips_blend": "PP, 50/50 nominal/TIPS bond sleeve",
    "pp_cash_buffer": "PP + 2y cash buffer", "pp_no_gold": "PP ablation: no gold (to cash)",
    "pp_no_long_duration": "PP ablation: no long bonds (to cash)", "best_static": "Best static equity/bond (train)",
    "pp_dynamic_weights": "Regime-adaptive PP (filtered signal)", "pp_robust": "Robust PP (minimax regret)",
}


class PermanentSpec(S.Frozen):
    data: S.StudyData = Field(default_factory=lambda: S.StudyData(universe="pp_modern_etf"))
    scenario: S.StudyScenario = Field(default_factory=lambda: S.StudyScenario(n_paths=2000))
    investor: S.StudyInvestor = Field(default_factory=lambda: S.StudyInvestor(horizon_years=30))
    preferences: S.StudyPrefs = Field(default_factory=S.StudyPrefs)
    costs: S.StudyCosts = Field(default_factory=lambda: S.StudyCosts(commission_bps=1, half_spread_bps=2))
    policies: tuple[str, ...] = tuple(POLICY_LABELS)
    withdrawal: float = Field(0.04, ge=0, le=0.15)
    withdrawal_grid: tuple[float, ...] = (0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08)
    horizons_years: tuple[int, ...] = (10, 20, 30)
    benchmark: str = "sixty_forty"
    long_bond: str = "ust_30y"
    gold: str = "gold"
    cash: str = "tbill"
    equity: str = "us_eq"
    duration_variants: tuple[str, ...] = ("ust_2y", "ust_5y", "ust_10y", "ust_30y")
    simplex_divisions: int = Field(10, ge=2, le=20)
    reserve_years: tuple[float, ...] = (0, 1, 2, 3, 5)
    cohort_years: int = Field(10, ge=5, le=40)
    label: str | None = None


def _sleeves(spec: PermanentSpec, assets: tuple[str, ...]) -> dict[str, str | None]:
    pick = lambda a: a if a in assets else None  # noqa: E731
    inter = pick("ust_10y") or pick("ust_5y")
    return {"eq": pick(spec.equity), "long": pick(spec.long_bond), "gold": pick(spec.gold), "cash": pick(spec.cash),
            "inter": inter, "tips": pick("tips"), "ten": pick("ust_10y") or pick(spec.long_bond)}


def _pp(sl: dict, long: str | None = None, gold: str | None = "gold", cash_extra: float = 0.0) -> dict[str, float]:
    w: dict[str, float] = {}

    def add(k, v):
        if k is None:
            raise S.IncompatibleUniverse("required sleeve missing from universe")
        w[k] = w.get(k, 0.0) + v
    add(sl["eq"], 0.25)
    add(long if long is not None else sl["long"], 0.25)
    if gold == "gold":
        add(sl["gold"], 0.25)
    else:
        add(sl["cash"], 0.25)
    add(sl["cash"], 0.25 + cash_extra)
    return w


def _policy_def(name: str, spec: PermanentSpec, sl: dict) -> tuple[dict[str, float], str, dict[str, Any]]:
    """(weights, strategy, strategy overrides)"""
    if name == "sixty_forty":
        if sl["eq"] is None or sl["ten"] is None:
            raise S.IncompatibleUniverse("60/40 needs equity and a Treasury sleeve")
        return {sl["eq"]: 0.6, sl["ten"]: 0.4}, "calendar_12m", {}
    if name == "pp_classic":
        return _pp(sl), "browne_15_35", {}
    if name == "pp_monthly":
        return _pp(sl), "calendar_1m", {}
    if name == "pp_annual":
        return _pp(sl), "calendar_12m", {}
    if name == "pp_15_35_monthly":
        return _pp(sl), "browne_15_35_monthly", {}
    if name == "pp_5pp_band":
        return _pp(sl), "absolute_band_5pp", {}
    if name == "pp_intermediate":
        if sl["inter"] is None:
            raise S.IncompatibleUniverse("no intermediate Treasury in universe")
        return _pp(sl, long=sl["inter"]), "browne_15_35", {}
    if name == "pp_tips_blend":
        if sl["tips"] is None:
            raise S.IncompatibleUniverse("no TIPS series in universe")
        w = _pp(sl)
        w[sl["long"]] -= 0.125
        w[sl["tips"]] = w.get(sl["tips"], 0) + 0.125
        return w, "browne_15_35", {}
    if name == "pp_cash_buffer":
        return _pp(sl), "browne_15_35", {"reserve_years": 2.0, "funding": "cash_first"}
    if name == "pp_no_gold":
        return _pp(sl, gold="cash"), "browne_15_35", {}
    if name == "pp_no_long_duration":
        w = _pp(sl)
        w[sl["cash"]] += w.pop(sl["long"])
        return w, "browne_15_35", {}
    raise ValueError("unknown or data-dependent policy " + name)


def _sched(w: dict[str, float], assets, T):
    return S.weights_vector(w, assets)


def _metrics(out, ctx, spec, gamma, horizons, iid) -> dict[str, Any]:
    T = ctx.tensor.n_months
    yrs = T / 12.0
    W = out.wealth_y
    m = {"ce": S.ce_block(out, gamma),
         "success": {str(h): S.success_block(out.first_shortfall, h * 12, iid) for h in horizons},
         "until_death": S.until_death_success(out.first_shortfall, ctx.survival),
         "severity": S.severity_block(out), "max_drawdown_median": float(np.median(out.max_drawdown)),
         "max_drawdown_p05": float(np.quantile(out.max_drawdown, 0.05)),
         "cost_bps_per_year": float(np.mean(out.cost / np.maximum(W[:, :-1].mean(axis=1), 1.0)) / yrs * 1e4)
         if W.shape[1] > 1 else None,
         "cost_usd_per_year": float(out.cost.mean() / yrs), "turnover_one_way_per_year": float(out.turnover.mean() / 2 / yrs),
         "trades_per_year": float(out.n_trades.mean() / yrs),
         "terminal_wealth": S.fan(out.terminal[:, None]), "first10y_shortfall": float(
             np.mean((out.first_shortfall >= 0) & (out.first_shortfall < 120)))}
    return m


def run_permanent(spec: PermanentSpec, progress: S.Progress) -> dict[str, Any]:
    u = S.universe_or_raise(spec.data)
    progress("generating_scenarios", 0.02)
    es, ctx, train = S.train_test(spec.data, spec.scenario, spec.investor, spec.preferences)
    ten = ctx.tensor
    assets = ten.assets
    T = ten.n_months
    sl = _sleeves(spec, assets)
    gamma = spec.preferences.gamma
    iid = ten.meta.get("generator") != "historical"
    horizons = tuple(h for h in spec.horizons_years if h <= spec.investor.horizon_years)
    cov = S.hist_cov(u, assets)
    uf = spec.preferences.util_floor_annual
    r0 = spec.withdrawal

    def ev(c, w, strat, over, rate=r0, record=True, tensor=None):
        tr = S.strategy(strat, spec.costs, **over)
        return S.run(c, _sched(w, assets, T), tr, rate=rate, record=record, cov=cov, util_floor=uf, tensor=tensor)

    outs: dict[str, Any] = {}
    defs: dict[str, Any] = {}
    unavailable: dict[str, str] = {}
    for name in spec.policies:
        try:
            if name == "best_static":
                best = None
                for e in np.linspace(0, 1, 11):
                    w = {sl["eq"]: e, sl["ten"]: 1 - e}
                    ce = S.ce_of(ev(train, w, "calendar_12m", {}, record=False), gamma)
                    if best is None or ce > best[0]:
                        best = (ce, w)
                defs[name] = (best[1], "calendar_12m", {})
            elif name == "pp_dynamic_weights":
                if ten.n_regimes <= 1:
                    raise S.IncompatibleUniverse("needs a regime-bearing generator (k_regimes > 1)")
                defs[name] = ("dynamic", "calendar_12m", {})
            elif name == "pp_robust":
                defs[name] = ("robust", "browne_15_35", {})
            else:
                defs[name] = _policy_def(name, spec, sl)
        except S.IncompatibleUniverse as exc:
            unavailable[name] = str(exc)
    progress("simulating", 0.15)
    # dynamic PP: per-regime defensive mix on a small grid (equity fixed 25%), fitted on training paths
    dyn_info = None
    if "pp_dynamic_weights" in defs:
        K = ten.n_regimes
        grid = []
        for g in (0.0, 0.125, 0.25, 0.375):
            for c in (0.125, 0.25, 0.375):
                b = 0.75 - g - c
                if b >= 0:
                    grid.append((b, g, c))
        def row(b, g, c):
            v = np.zeros(len(assets))
            v[assets.index(sl["eq"])] = 0.25
            v[assets.index(sl["long"])] += b
            v[assets.index(sl["gold"] or sl["cash"])] += g
            v[assets.index(sl["cash"])] += c
            return v

        per = np.array([row(0.25, 0.25, 0.25) for _ in range(K)])
        for k in range(K):  # coordinate search, one regime at a time, on training paths only
            best = None
            for b, g, c in grid:
                trial = per.copy()
                trial[k] = row(b, g, c)
                sched = np.broadcast_to(trial, (T, K, len(assets))).copy()
                o = S.run(train, sched, S.strategy("calendar_12m", spec.costs), rate=r0, util_floor=uf)
                ce = S.ce_of(o, gamma)
                if best is None or ce > best[0]:
                    best = (ce, trial[k].copy())
            per[k] = best[1]
        dyn_info = {"per_regime": {str(k): dict(zip(assets, np.round(per[k], 4).tolist())) for k in range(K)},
                    "signal": ten.meta.get("decision_signal"), "grid_size": len(grid)}
        defs["pp_dynamic_weights"] = (np.broadcast_to(per, (T, K, len(assets))).copy(), "calendar_12m", {})
    # robust PP: minimax regret across generators on the defensive simplex grid (equity fixed 25%)
    robust_info = None
    if "pp_robust" in defs:
        cands = []
        for g in (0.0, 0.125, 0.25):
            for c in (0.125, 0.25, 0.375):
                b = 0.75 - g - c
                if b >= 0 and (sl["gold"] or g == 0):
                    cands.append((b, g, c))
        gens = ["bootstrap", "student_t"]
        table = np.zeros((len(gens), len(cands)))
        for gi, gname in enumerate(gens):
            try:
                es_g = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences, generator=gname,
                                         n_paths=800, seed=spec.scenario.seed + 101)
                tg = S.get_tensor(es_g)
                cg = S.get_context(es_g, tg, es_g.scenario.seed)
            except Exception:
                continue
            for ci, (b, g, c) in enumerate(cands):
                w = {sl["eq"]: 0.25, sl["long"]: b, sl["cash"]: c}
                if g > 0:
                    w[sl["gold"]] = g
                table[gi, ci] = S.ce_of(S.run(cg, S.weights_vector(w, assets), S.strategy("browne_15_35", spec.costs),
                                              rate=r0, util_floor=uf), gamma)
        regret = (table.max(axis=1, keepdims=True) - table) / np.maximum(table.max(axis=1, keepdims=True), 1e-9)
        ci = int(np.argmin(regret.max(axis=0)))
        b, g, c = cands[ci]
        w = {sl["eq"]: 0.25, sl["long"]: b, sl["cash"]: c}
        if g > 0:
            w[sl["gold"]] = g
        defs["pp_robust"] = (w, "browne_15_35", {})
        robust_info = {"candidates": [list(x) for x in cands], "generators": gens, "ce": S.to_list(table, 2),
                       "max_regret": S.to_list(regret.max(axis=0)), "chosen": list(cands[ci])}
    k = 0
    for name, (w, strat, over) in defs.items():
        if isinstance(w, np.ndarray):
            o = S.run(ctx, w, S.strategy(strat, spec.costs, **over), rate=r0, record=True, cov=cov, util_floor=uf)
        else:
            o = ev(ctx, w, strat, over)
        outs[name] = o
        k += 1
        progress("simulating", 0.15 + 0.3 * k / max(len(defs), 1))
    bname = spec.benchmark if spec.benchmark in outs else next(iter(outs), None)
    if bname is None:
        raise S.IncompatibleUniverse("no policy could be evaluated on universe %s: %s" % (u.name, unavailable))
    bo = outs[bname]
    mh = max(horizons)
    score = []
    for name, o in outs.items():
        m = _metrics(o, ctx, spec, gamma, horizons, iid)
        m["policy"] = name
        m["label"] = POLICY_LABELS.get(name, name)
        w, strat, over = defs[name]
        m["weights"] = (dict(zip(assets, np.round(S.weights_vector(w, assets), 4).tolist())) if isinstance(w, dict)
                        else "regime-dependent")
        m["rebalancer"] = strat + ("+" + ",".join("%s=%s" % kv for kv in over.items()) if over else "")
        if name != bname:
            m["delta_ce_vs_benchmark"] = S.delta_block(o, bo, gamma)
            m["delta_success_vs_benchmark"] = S.paired_success_diff(S.success(o.first_shortfall, mh * 12),
                                                                    S.success(bo.first_shortfall, mh * 12))
        score.append(m)

    # PP-01 sleeve matrix with history-based exposures
    progress("summarising", 0.5)
    sleeves = []
    hist = u.real
    infl = u.inflation
    eq_h = hist[sl["eq"]] if sl["eq"] else None
    pp_o = outs.get("pp_classic")
    for key in ("eq", "long", "gold", "cash"):
        a = sl[key]
        if a is None:
            sleeves.append({"sleeve": key, "available": False,
                            "reason": unavailable.get("pp_classic", "series not in universe")})
            continue
        x = hist[a]
        beta_eq = float(np.cov(x, eq_h)[0, 1] / np.var(eq_h)) if eq_h is not None else None
        nom = u.nominal[a]
        beta_inf = float(np.cov(nom, infl)[0, 1] / np.var(infl))
        actual = float(pp_o.weights_y[:, :, assets.index(a)].mean()) if pp_o is not None else None
        prov = S.provenance((a,))[a]
        sleeves.append({"sleeve": key, "asset": a, "label": panel.asset_label(a), "available": True, "target": 0.25,
                        "actual_mean_weight": actual, "purpose": SLEEVE_INFO.get(a, ("", ""))[0] if a in SLEEVE_INFO
                        else {"eq": SLEEVE_INFO["us_eq"][0], "long": SLEEVE_INFO["ust_30y"][0], "gold": SLEEVE_INFO["gold"][0],
                              "cash": SLEEVE_INFO["tbill"][0]}[key],
                        "risk_exposure": {"real_vol": float(x.std() * np.sqrt(12)), "equity_beta": beta_eq,
                                          "inflation_beta_nominal": beta_inf, "real_mean": float(x.mean() * 12)},
                        "source": prov})

    # PP-03 conditional advantage: withdrawal x starting regime (and all starts), paired dCE vs benchmark
    progress("conditional", 0.55)
    cond = {"r": list(spec.withdrawal_grid), "rows": []}
    ref = "pp_classic" if "pp_classic" in defs else ("pp_no_gold" if "pp_no_gold" in defs else None)
    target_pol = ref if ref is not None else next((p for p in defs if p != bname), None)
    if target_pol is not None:
        starts: list[tuple[str, int | None]] = [("all starts", None)]
        if ten.n_regimes > 1:
            starts += [("start regime %d" % k_, k_) for k_ in range(ten.n_regimes)]
        for lab, sr in starts:
            row = {"label": lab, "delta": [], "lo": [], "hi": [], "d_success": []}
            if sr is None:
                c2 = ctx
            else:
                t2 = S.get_tensor(es, n_paths=min(spec.scenario.n_paths, 1000), start_regime=sr,
                                  seed=spec.scenario.seed + 17)
                c2 = S.get_context(es, t2, spec.scenario.seed + 17)
            wp, sp, op = defs[target_pol]
            wb, sb, ob = defs[bname]
            for r in spec.withdrawal_grid:
                op_ = ev(c2, wp, sp, op, rate=r, record=False) if not isinstance(wp, np.ndarray) else S.run(
                    c2, wp, S.strategy(sp, spec.costs), rate=r, util_floor=uf)
                ob_ = ev(c2, wb, sb, ob, rate=r, record=False)
                d = S.delta_block(op_, ob_, gamma, n_boot=100)
                row["delta"].append(d["delta"])
                row["lo"].append(d["lo"])
                row["hi"].append(d["hi"])
                row["d_success"].append(float(S.success(op_.first_shortfall, mh * 12).mean() -
                                              S.success(ob_.first_shortfall, mh * 12).mean()))
            cond["rows"].append(row)
        cond["policy"] = target_pol
        cond["benchmark"] = bname

    # PP-04 macro regime quadrants from the observed history (descriptive, lagged classification)
    quadrants = _quadrants(u, sl, defs, assets)

    # PP-05 dynamic weight river: expected weights by year given the share of paths in each signal state
    river = None
    if dyn_info is not None:
        dec = ten.decision_regime()
        K = ten.n_regimes
        per = defs["pp_dynamic_weights"][0][0]
        years = T // 12
        shares = np.array([[np.mean(dec[:, y * 12] == k_) for k_ in range(K)] for y in range(years)])
        river = {"years": list(range(years)), "regime_share": S.to_list(shares, 4),
                 "expected_weights": S.to_list(shares @ per, 4), "assets": list(assets), **dyn_info}

    # PP-06 gold: ablation by start regime + descriptive hedge statistics
    gold_block: dict[str, Any] = {"available": sl["gold"] is not None}
    if sl["gold"] is not None and "pp_classic" in outs and "pp_no_gold" in outs:
        rows = [{"label": "all starts", **S.delta_block(outs["pp_classic"], outs["pp_no_gold"], gamma, n_boot=100)}]
        if ten.n_regimes > 1:
            for k_ in range(ten.n_regimes):
                t2 = S.get_tensor(es, n_paths=min(spec.scenario.n_paths, 1000), start_regime=k_,
                                  seed=spec.scenario.seed + 23)
                c2 = S.get_context(es, t2, spec.scenario.seed + 23)
                a_ = ev(c2, defs["pp_classic"][0], "browne_15_35", {}, record=False)
                b_ = ev(c2, defs["pp_no_gold"][0], "browne_15_35", {}, record=False)
                rows.append({"label": "start regime %d" % k_, **S.delta_block(a_, b_, gamma, n_boot=100)})
        g = u.nominal[sl["gold"]]
        e = u.nominal[sl["eq"]]
        worst = e <= e.quantile(0.1)
        yoy = (1 + infl).rolling(12).apply(np.prod, raw=True) - 1
        hi_inf = (yoy.shift(1) > 0.03)
        gold_block.update({"incremental_ce": rows,
                           "p_gold_loss_given_equity_worst_decile": float((g[worst] < 0).mean()),
                           "p_gold_loss_unconditional": float((g < 0).mean()),
                           "corr_gold_cpi_high_inflation": float(np.corrcoef(g[hi_inf], infl[hi_inf])[0, 1])
                           if hi_inf.sum() > 24 else None,
                           "corr_gold_cpi_low_inflation": float(np.corrcoef(g[~hi_inf], infl[~hi_inf])[0, 1])
                           if (~hi_inf).sum() > 24 else None,
                           "n_months": int(len(g)), "window": [u.start.date().isoformat(), u.end.date().isoformat()],
                           "lag": "inflation regime classified on YoY CPI known at t-1 (15-day CPI publication lag)"})
    elif sl["gold"] is None:
        gold_block["reason"] = "no observed gold series in universe %s" % u.name

    # PP-07 duration replacement small multiples (cash and gold held constant)
    progress("duration", 0.65)
    dur_rows = []
    try:
        curve_d, cm, cz = _curve()
    except Exception:
        cm = cz = None
        curve_d = None
    for a in spec.duration_variants:
        if a not in assets:
            dur_rows.append({"asset": a, "available": False})
            continue
        w = _pp(sl, long=a, gold="gold" if sl["gold"] else "cash")
        o = ev(ctx, w, "browne_15_35", {})
        mat = float(a.split("_")[1][:-1])
        yld = float(np.interp(mat, cm, cz)) if cm is not None else 0.04
        dmod = fixed_income.modified_duration(yld, yld, mat)
        dur_rows.append({"asset": a, "available": True, "maturity": mat, "ce": S.ce_of(o, gamma),
                         "success": float(S.success(o.first_shortfall, mh * 12).mean()),
                         "cvar95_unmet": S.cvar(o.unmet, 0.95), "modified_duration": dmod,
                         "dv01_per_1m_sleeve": fixed_income.dv01(yld, yld, mat) * 1e6 / 100.0,
                         "portfolio_duration": 0.25 * dmod, "yield_used": yld, "curve_date": curve_d})

    # PP-08 cash buffer trade-off (paired against no buffer)
    progress("cash buffer", 0.72)
    cash_rows = []
    if ref is not None and sl["cash"] is not None:
        base = None
        for ry in spec.reserve_years:
            o = ev(ctx, defs[ref][0], "browne_15_35", {"reserve_years": float(ry), "funding": "cash_first"}
                   if ry > 0 else {})
            if base is None:
                base = o
            row = {"reserve_years": ry, "ce": S.ce_of(o, gamma),
                   "first10y_shortfall": float(np.mean((o.first_shortfall >= 0) & (o.first_shortfall < 120))),
                   "median_terminal": float(np.median(o.terminal)),
                   "growth_sacrifice_median_terminal": float(np.median(o.terminal) - np.median(base.terminal))}
            if ry > 0:
                row["delta_ce"] = S.delta_block(o, base, gamma, n_boot=100)
                row["delta_first10y"] = S.paired_success_diff((o.first_shortfall >= 0) & (o.first_shortfall < 120),
                                                              (base.first_shortfall >= 0) & (base.first_shortfall < 120))
            cash_rows.append(row)

    # PP-09 defensive-mix simplex (equity fixed at 25%)
    progress("simplex", 0.8)
    simplex = []
    n = spec.simplex_divisions
    for i in range(n + 1):
        for j in range(n + 1 - i):
            kk = n - i - j
            b, g, c = 0.75 * i / n, 0.75 * j / n, 0.75 * kk / n
            if g > 0 and sl["gold"] is None:
                simplex.append({"bond": b, "gold": g, "cash": c, "masked": True,
                                "reason": "gold not in universe"})
                continue
            w = {sl["eq"]: 0.25}
            for a_, v in ((sl["long"], b), (sl["gold"], g), (sl["cash"], c)):
                if v > 0:
                    w[a_] = w.get(a_, 0) + v
            o = ev(ctx, w, "browne_15_35", {}, record=False)
            simplex.append({"bond": b, "gold": g, "cash": c, "masked": False, "ce": S.ce_of(o, gamma),
                            "success": float(S.success(o.first_shortfall, mh * 12).mean())})

    # PP-11 historical cohort race
    progress("cohorts", 0.86)
    cohorts = _cohorts(spec, u, defs, bname)

    # PP-12 ablation / Shapley over sleeves {gold, nominal duration, real duration, cash}
    progress("shapley", 0.92)
    shap = _shapley(spec, ctx, sl, assets, gamma, uf, r0)

    return {"kind": "permanent", "universe": S.universe_block(u), "scenario": S.scenario_block(ten),
            "n_paths": ten.n_paths, "withdrawal": r0, "horizons": list(horizons), "benchmark": bname,
            "unavailable": unavailable, "scorecard": score, "sleeves": sleeves, "conditional": cond,
            "quadrants": quadrants, "river": river, "gold": gold_block, "duration": dur_rows, "cash_buffer": cash_rows,
            "simplex": simplex, "cohorts": cohorts, "shapley": shap, "robust": robust_info, "reference_pp": ref,
            "costs": spec.costs.model_dump(), "sample_note": "all policies share one tensor, spending rule, costs "
                                                             "and horizon (paired comparisons)",
            "warnings": S.common_warnings(u, ten), "timings": {},
            "summary": {"universe": u.name, "n_policies": len(outs), "unavailable": len(unavailable)}}


def _curve():
    ids = ["gsw_nom_%02d" % m for m in range(1, 31)]
    w = panel.wide(ids).dropna()
    row = w.iloc[-1]
    return w.index[-1].date().isoformat(), np.array([int(c[-2:]) for c in row.index], float), row.to_numpy()


def _quadrants(u, sl, defs, assets) -> dict[str, Any]:
    """Growth x inflation quadrants classified with information available one month earlier."""
    try:
        ip = panel.series("s_indpro").reindex(u.real.index)
    except KeyError:
        return {"available": False, "reason": "industrial production not in panel"}
    infl = u.inflation
    g_yoy = ip.pct_change(12)
    i_yoy = (1 + infl).rolling(12).apply(np.prod, raw=True) - 1
    g_lag = g_yoy.shift(2)   # INDPRO published ~16 days after month end -> known by end of next month
    i_lag = i_yoy.shift(1)
    g_med = g_lag.expanding(120).median()
    i_med = i_lag.expanding(120).median()
    ok = g_lag.notna() & i_lag.notna() & g_med.notna() & i_med.notna()
    labels = {(True, True): "rising growth / rising inflation", (True, False): "rising growth / falling inflation",
              (False, True): "falling growth / rising inflation", (False, False): "falling growth / falling inflation"}
    out = []
    port = {}
    for name in ("pp_classic", "sixty_forty", "pp_no_gold"):
        if name in defs and isinstance(defs[name][0], dict):
            port[name] = S.weights_vector(defs[name][0], assets)
    R = u.real[list(assets)].to_numpy()
    for (gh, ih), lab in labels.items():
        m = (ok & ((g_lag > g_med) == gh) & ((i_lag > i_med) == ih)).to_numpy()
        n = int(m.sum())
        row = {"quadrant": lab, "n_months": n, "assets": {}, "portfolios": {}}
        if n >= 12:
            for i, a in enumerate(assets):
                x = R[m, i]
                row["assets"][a] = {"mean_annual": float(x.mean() * 12), "se_annual": float(x.std() / np.sqrt(n) * 12)}
            for pn, w in port.items():
                x = R[m] @ w
                row["portfolios"][pn] = {"mean_annual": float(x.mean() * 12), "se_annual": float(x.std() / np.sqrt(n) * 12)}
        out.append(row)
    first = u.real.index[ok.to_numpy()][0].date().isoformat() if ok.any() else None
    return {"available": True, "rows": out, "window": [first, u.end.date().isoformat()],
            "method": "YoY industrial production (lag 2m) and YoY CPI (lag 1m) vs their expanding medians "
                      "(min 10y); simple monthly returns, real; SE assumes independence (understates for "
                      "persistent regimes)", "caveat": "economic labels only; no deterministic asset ranking"}


def _cohorts(spec, u, defs, bname) -> dict[str, Any]:
    months = spec.cohort_years * 12
    if len(u.real) < months + 12:
        return {"available": False, "reason": "history shorter than the cohort horizon"}
    d2 = spec.data
    sc = spec.scenario.model_copy(update={"generator": "historical"})
    inv = spec.investor.model_copy(update={"horizon_years": spec.cohort_years})
    try:
        es = S.experiment_spec(d2, sc, inv, spec.preferences, generator="historical")
        ten = S.get_tensor(es)
        ctx = S.get_context(es, ten, es.scenario.seed)
    except Exception as exc:
        return {"available": False, "reason": str(exc)}
    from lifecycle.runs import context as C

    model = C.fitted_model(es)
    starts = list(getattr(model, "last_starts", []))
    res = {"available": True, "starts": starts[:ten.n_paths], "years": spec.cohort_years, "policies": {},
           "caveat": "overlapping cohorts share most of their returns: they are not independent trials"}
    base = None
    if bname in defs and isinstance(defs[bname][0], dict):
        base = S.run(ctx, S.weights_vector(defs[bname][0], ten.assets), S.strategy(defs[bname][1], spec.costs),
                     rate=spec.withdrawal, util_floor=spec.preferences.util_floor_annual)
    for name in ("pp_classic", "pp_no_gold", "pp_intermediate", bname):
        if name not in defs or not isinstance(defs[name][0], dict):
            continue
        w, strat, over = defs[name]
        o = S.run(ctx, S.weights_vector(w, ten.assets), S.strategy(strat, spec.costs, **over), rate=spec.withdrawal,
                  util_floor=spec.preferences.util_floor_annual)
        rel = (o.terminal / np.maximum(base.terminal, 1.0)).tolist() if base is not None else None
        res["policies"][name] = {"terminal": S.to_list(o.terminal, 0), "relative_terminal": S.to_list(rel, 4),
                                 "funded": S.to_list(o.funded, 0), "shortfall": (o.first_shortfall >= 0).tolist()}
    return res


def _shapley(spec, ctx, sl, assets, gamma, uf, r0) -> dict[str, Any]:
    players = [p for p in (("gold", sl["gold"]), ("nominal duration", sl["long"]), ("real duration", sl["tips"]),
                           ("cash", sl["cash"])) if p[1] is not None]
    names = [p[0] for p in players]
    cache: dict[frozenset, float] = {}

    def value(coal: frozenset) -> float:
        if coal in cache:
            return cache[coal]
        if len(coal) == 0:
            w = {sl["eq"]: 1.0}
        else:
            w = {sl["eq"]: 0.25}
            for nm, a in players:
                if nm in coal:
                    w[a] = w.get(a, 0) + 0.75 / len(coal)
        o = S.run(ctx, S.weights_vector(w, assets), S.strategy("browne_15_35" if coal else "none_buyhold", spec.costs),
                  rate=r0, util_floor=uf)
        cache[coal] = S.ce_of(o, gamma)
        return cache[coal]

    n = len(names)
    phi = {}
    for p in names:
        tot = 0.0
        others = [q for q in names if q != p]
        for k in range(n):
            for comb in combinations(others, k):
                s = frozenset(comb)
                wgt = factorial(k) * factorial(n - k - 1) / factorial(n)
                tot += wgt * (value(s | {p}) - value(s))
        phi[p] = tot
    v_full = value(frozenset(names))
    v_empty = value(frozenset())
    alone = {p: value(frozenset({p})) - v_empty for p in names}
    return {"players": names, "shapley_ce_usd": phi, "v_full": v_full, "v_empty": v_empty, "alone": alone,
            "interaction": v_full - v_empty - sum(alone.values()),
            "baseline": "empty coalition = 100% equity, no rebalancing; coalition S = 25% equity + 75% split "
                        "equally over S; Shapley values sum to v(full) - v(empty)",
            "note": "values are not additive: the interaction term shows the gap between stand-alone gains and the "
                    "full-portfolio gain"}
