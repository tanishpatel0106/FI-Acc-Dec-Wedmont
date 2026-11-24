"""Page J: paired policy comparison, cohort winners, attribution waterfall and robustness forest."""
from itertools import combinations
from math import factorial
from typing import Any

import numpy as np
from pydantic import Field

from lifecycle.data import panel
from lifecycle.engine.lifecycle.policies import target_date_equity
from lifecycle.studies import common as S

POLICIES = {
    "sixty_forty": ({"us_eq": 0.6, "ust_10y": 0.4}, "calendar_12m"),
    "all_equity": ({"us_eq": 1.0}, "calendar_12m"),
    "forty_sixty": ({"us_eq": 0.4, "ust_10y": 0.6}, "calendar_12m"),
    "pp_ex_gold": ({"us_eq": 0.25, "ust_30y": 0.25, "tbill": 0.5}, "browne_15_35"),
    "equity_cash_buffer": ({"us_eq": 0.7, "ust_10y": 0.2, "tbill": 0.1}, "cash_first_floor"),
    "target_date": ("target_date", "calendar_12m"),
}


class CompareV2Spec(S.Frozen):
    data: S.StudyData = Field(default_factory=lambda: S.StudyData(universe="core_duration"))
    scenario: S.StudyScenario = Field(default_factory=lambda: S.StudyScenario(n_paths=2000))
    investor: S.StudyInvestor = Field(default_factory=lambda: S.StudyInvestor(horizon_years=30))
    preferences: S.StudyPrefs = Field(default_factory=S.StudyPrefs)
    costs: S.StudyCosts = Field(default_factory=lambda: S.StudyCosts(commission_bps=1, half_spread_bps=2))
    policies: tuple[str, ...] = tuple(POLICIES)
    benchmark: str = "sixty_forty"
    focus: str = "target_date"
    withdrawal: float = 0.045
    cohort_years: int = 25
    generators: tuple[str, ...] = ("bootstrap", "student_t", "markov_switching", "historical")
    windows: tuple[tuple[str, str], ...] = (("1977-01-01", "2001-12-31"), ("2002-01-01", "2026-12-31"))
    label: str | None = None


def _sched(name: str, assets, T, start_age):
    w, strat = POLICIES[name]
    if w == "target_date":
        ages = start_age + np.arange(T) / 12.0
        e = target_date_equity(ages)
        sched = np.zeros((T, 1, len(assets)))
        sched[:, 0, assets.index("us_eq")] = e
        sched[:, 0, assets.index("ust_10y")] = 1 - e
        return sched, strat
    return S.weights_vector(w, assets), strat


def run_compare_v2(spec: CompareV2Spec, progress: S.Progress) -> dict[str, Any]:
    u = S.universe_or_raise(spec.data)
    es = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences)
    ten = S.get_tensor(es)
    ctx = S.get_context(es, ten, es.scenario.seed)
    assets = ten.assets
    T = ten.n_months
    gamma = spec.preferences.gamma
    mh = spec.investor.horizon_years * 12
    uf = spec.preferences.util_floor_annual
    outs = {}
    for name in spec.policies:
        sc, strat = _sched(name, assets, T, spec.investor.age)
        outs[name] = S.run(ctx, sc, S.strategy(strat, spec.costs), rate=spec.withdrawal, record=True, util_floor=uf)
    progress("paired statistics", 0.3)
    b = outs[spec.benchmark]
    k = min(500, ten.n_paths)
    forest, table = [], []
    pce_b = np.array(S.path_ces(b, gamma, ten.n_paths))
    for name, o in outs.items():
        sb = S.success(o.first_shortfall, mh)
        avgW = np.maximum(o.wealth_y[:, :-1].mean(axis=1), 1.0)
        prov = S.provenance(assets)
        row = {"policy": name, "ce": S.ce_of(o, gamma), "success": float(sb.mean()),
               "unmet_mean": float(o.unmet.mean()), "mdd_median": float(np.median(o.max_drawdown)),
               "cost_bps_yr": float(np.mean(o.cost / avgW) / (T / 12) * 1e4),
               "duration_proxy": None, "data_quality": "model_generated" if any(
                   v["provenance"] == "model_generated" for v in prov.values()) else "observed"}
        table.append(row)
        if name != spec.benchmark:
            d = S.delta_block(o, b, gamma)
            forest.append({"policy": name, **d})
    # CO-02 paired path scatter for the focus policy; CO-04 divergent paths with early sequence explanation
    fo = outs.get(spec.focus, next(iter(outs.values())))
    pce_f = np.array(S.path_ces(fo, gamma, ten.n_paths))
    scatter = {"benchmark_ce": np.round(pce_b[:k], 1).tolist(), "policy_ce": np.round(pce_f[:k], 1).tolist(),
               "policy_failed": (fo.first_shortfall[:k] >= 0).tolist(), "benchmark_failed": (b.first_shortfall[:k] >= 0).tolist()}
    diff = pce_f - pce_b
    order = np.argsort(diff)
    eq = ten.real_returns[:, :, assets.index("us_eq")]
    early = np.prod(1 + eq[:, :60], axis=1) - 1
    infl = np.prod(1 + ten.inflation[:, :60], axis=1) - 1
    divergent = []
    for lab, idxs in (("largest negative", order[:5]), ("largest positive", order[-5:][::-1])):
        for j in idxs:
            divergent.append({"group": lab, "path": int(j), "delta_path_ce": float(diff[j]),
                              "benchmark_first_shortfall_year": None if b.first_shortfall[j] < 0 else float(b.first_shortfall[j] / 12),
                              "policy_first_shortfall_year": None if fo.first_shortfall[j] < 0 else float(fo.first_shortfall[j] / 12),
                              "equity_real_return_first_5y": float(early[j]), "cpi_first_5y": float(infl[j]),
                              "terminal_policy": float(fo.terminal[j]), "terminal_benchmark": float(b.terminal[j])})
    twin = {"policy": {"wealth": S.fan(fo.wealth_y), "consumption": S.fan(fo.cons_y)},
            "benchmark": {"wealth": S.fan(b.wealth_y), "consumption": S.fan(b.cons_y)},
            "ages": (spec.investor.age + np.arange(fo.wealth_y.shape[1])).tolist()}

    # CO-05 cohort winner matrix and CO-10 first-failure timeline (historical cohorts)
    progress("cohorts", 0.45)
    cohorts: dict[str, Any] = {"available": False}
    try:
        inv_c = spec.investor.model_copy(update={"horizon_years": spec.cohort_years})
        esh = S.experiment_spec(spec.data, spec.scenario, inv_c, spec.preferences, generator="historical")
        th = S.get_tensor(esh)
        ch = S.get_context(esh, th, esh.scenario.seed)
        from lifecycle.runs import context as C

        starts = list(getattr(C.fitted_model(esh), "last_starts", []))[: th.n_paths]
        years = sorted({s[:4] for s in starts})
        first_by_year = [starts.index(next(s for s in starts if s.startswith(y))) for y in years]
        hb = None
        mat_d, mat_s = [], []
        hist_out = {}
        for name in spec.policies:
            sc, strat = _sched(name, th.assets, th.n_months, spec.investor.age)
            o = S.run(ch, sc, S.strategy(strat, spec.costs), rate=spec.withdrawal, record=True, util_floor=uf)
            hist_out[name] = o
        hb = hist_out[spec.benchmark]
        pb = np.array(S.path_ces(hb, gamma, th.n_paths))
        for name, o in hist_out.items():
            pp = np.array(S.path_ces(o, gamma, th.n_paths))
            mat_d.append([float(pp[i] / max(pb[i], 1e-9) - 1) for i in first_by_year])
            mat_s.append([bool(S.success(o.first_shortfall[i:i + 1], spec.cohort_years * 12)[0]) for i in first_by_year])
        worst = int(np.argmin(pb))
        fo_h = hist_out.get(spec.focus, hb)
        timeline = {"cohort_start": starts[worst], "policy": spec.focus,
                    "years": list(range(spec.cohort_years)),
                    "desired": S.to_list(fo_h.desired_y[worst], 0), "funded": S.to_list(fo_h.cons_y[worst], 0),
                    "unmet": S.to_list(fo_h.unmet_y[worst], 0), "benchmark_unmet": S.to_list(hb.unmet_y[worst], 0),
                    "first_shortfall_year": None if fo_h.first_shortfall[worst] < 0 else float(fo_h.first_shortfall[worst] / 12)}
        cohorts = {"available": True, "years": years, "policies": list(hist_out), "delta_path_ce": mat_d,
                   "success": mat_s, "coverage": [u.start.date().isoformat(), u.end.date().isoformat()],
                   "timeline": timeline, "caveat": "one cohort per start year shown; cohorts overlap (not independent)"}
    except Exception as exc:
        cohorts = {"available": False, "reason": str(exc)}

    # CO-07 attribution: allocation, spending rule, rebalancing, costs (sequential + Shapley over 4 factors)
    progress("attribution", 0.6)
    factors = ["allocation", "spending", "rebalancing", "costs"]
    fsched, _ = _sched(spec.focus, assets, T, spec.investor.age) if spec.focus in POLICIES else (S.weights_vector(
        {"us_eq": 0.6, "ust_10y": 0.4}, assets), None)
    bw = S.weights_vector(POLICIES[spec.benchmark][0], assets) if isinstance(POLICIES[spec.benchmark][0], dict) else fsched
    cache: dict[frozenset, float] = {}

    def v(coal: frozenset) -> float:
        if coal in cache:
            return cache[coal]
        sched = fsched if "allocation" in coal else bw
        spend = "guardrails" if "spending" in coal else "fixed_real"
        strat = "absolute_band_5pp" if "rebalancing" in coal else "calendar_12m"
        costs = S.StudyCosts(commission_bps=5, half_spread_bps=10) if "costs" in coal else S.StudyCosts()
        o = S.run(ctx, sched, S.strategy(strat, costs), rate=spec.withdrawal, spend=spend, util_floor=uf)
        cache[coal] = S.ce_of(o, gamma)
        return cache[coal]

    base_v = v(frozenset())
    seq, acc = [], frozenset()
    for f in factors:
        nxt = acc | {f}
        seq.append({"factor": f, "delta_ce_usd": v(nxt) - v(acc)})
        acc = nxt
    n = len(factors)
    shap = {}
    for f in factors:
        others = [x for x in factors if x != f]
        tot = 0.0
        for kk in range(n):
            for comb in combinations(others, kk):
                s = frozenset(comb)
                tot += factorial(kk) * factorial(n - kk - 1) / factorial(n) * (v(s | {f}) - v(s))
        shap[f] = tot
    attribution = {"base_ce": base_v, "full_ce": v(frozenset(factors)), "sequential": seq, "shapley": shap,
                   "definitions": {"allocation": "%s targets instead of %s" % (spec.focus, spec.benchmark),
                                   "spending": "Guyton-Klinger-style guardrails instead of fixed real",
                                   "rebalancing": "5pp band instead of annual calendar",
                                   "costs": "5bps commission + 10bps half spread instead of zero"},
                   "note": "sequential attribution is order-dependent; the Shapley split over the four factors is "
                           "order-free and sums to the total. Guardrails change spending itself, so this is a "
                           "joint spending-plus-allocation comparison."}

    # CO-08 regime robustness forest across generators and calibration windows
    progress("robustness", 0.75)
    rob = []
    for g in spec.generators:
        for w0, w1 in ((None, None),) + tuple(spec.windows):
            lab = g + ("" if w0 is None else " %s..%s" % (w0[:4], w1[:4]))
            try:
                d2 = spec.data if w0 is None else spec.data.model_copy(update={"calibration_start": w0, "calibration_end": w1})
                inv2 = spec.investor if g != "historical" else spec.investor.model_copy(update={"horizon_years": 20})
                es2 = S.experiment_spec(d2, spec.scenario, inv2, spec.preferences, generator=g, n_paths=800)
                t2 = S.get_tensor(es2)
                c2 = S.get_context(es2, t2, es2.scenario.seed)
                sc, strat = _sched(spec.focus, t2.assets, t2.n_months, spec.investor.age)
                o = S.run(c2, sc, S.strategy(strat, spec.costs), rate=spec.withdrawal, util_floor=uf)
                bsc, bst = _sched(spec.benchmark, t2.assets, t2.n_months, spec.investor.age)
                ob = S.run(c2, bsc, S.strategy(bst, spec.costs), rate=spec.withdrawal, util_floor=uf)
                d = S.delta_block(o, ob, gamma, n_boot=100)
                rob.append({"label": lab, "generator": g, "window": [w0, w1], **d,
                            "iid": g != "historical"})
            except Exception as exc:
                rob.append({"label": lab, "generator": g, "error": str(exc)[:200]})
    signs = {np.sign(r["delta"]) for r in rob if "delta" in r and r.get("significant")}
    # CO-09 public vs WRDS source substitution
    sub = _source_substitution()
    return {"kind": "compare_v2", "universe": S.universe_block(u), "n_paths": ten.n_paths, "benchmark": spec.benchmark,
            "focus": spec.focus, "withdrawal": spec.withdrawal, "forest": forest, "table": table, "scatter": scatter,
            "divergent": divergent, "twin_fan": twin, "cohorts": cohorts, "attribution": attribution,
            "robustness": rob, "sign_reversal": len(signs) > 1, "source_substitution": sub,
            "warnings": S.common_warnings(u, ten), "timings": {},
            "summary": {"universe": u.name, "focus": spec.focus, "sign_reversal": len(signs) > 1}}


def _source_substitution() -> dict[str, Any]:
    import pandas as pd

    from lifecycle.config import processed_dir

    p = processed_dir() / "panel_all_sources.parquet"
    if not p.exists():
        return {"available": False, "reason": "no multi-source panel on disk"}
    allp = pd.read_parquet(p)
    rows = []
    for sid, grp in allp[allp["quantity"] == "total_return"].groupby("series_id"):
        srcs = grp["source"].unique()
        if len(srcs) < 2:
            continue
        wide = grp.pivot_table(index="month_end", columns="source", values="value").dropna()
        if len(wide) < 24:
            continue
        a, b = wide.columns[:2]
        rows.append({"series_id": sid, "sources": [a, b], "overlap_months": int(len(wide)),
                     "mean_diff_annual": float((wide[a] - wide[b]).mean() * 12),
                     "tracking_error_annual": float((wide[a] - wide[b]).std() * np.sqrt(12)),
                     "corr": float(wide[a].corr(wide[b]))})
    if not rows:
        return {"available": False, "reason": "only one source per series (WRDS not ingested): public-repriced vs "
                                              "WRDS-observed comparison needs both on the same calendar"}
    return {"available": True, "rows": rows}


__all__ = ["CompareV2Spec", "run_compare_v2", "panel"]
