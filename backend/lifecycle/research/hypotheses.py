"""Pre-registered hypotheses H1-H4 (brief section 6): statistics, benchmarks, falsification rules."""
from collections.abc import Callable
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict

from lifecycle.engine.optimize import grid_dp
from lifecycle.engine.scenarios.bootstrap import StationaryBootstrap
from lifecycle.runs import context as C
from lifecycle.runs import registry
from lifecycle.runs.dp_job import build_problem, h1_slope, policy_surfaces
from lifecycle.runs.spec import ExperimentSpec, InvestorSpec, PolicySpec, ScenarioSpec

Progress = Callable[[str, float], None]


class HypothesesSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    sweep_id: str | None = None
    attribution_id: str | None = None
    gammas: tuple[float, ...] = (2.0, 4.0, 6.0)
    n_boot: int = 5
    h1_ages: tuple[float, ...] = (55.0, 70.0)
    min_effect: float = 0.005


def _slopes_at(surfaces: dict[str, Any], ages: tuple[float, ...]) -> list[float]:
    rows = h1_slope(surfaces)
    out = []
    for a in ages:
        near = [r["slope"] for r in rows if abs(r["age"] - a) < 2.6]
        out.append(float(np.mean(near)) if near else float("nan"))
    return out


def test_h1(spec: HypothesesSpec, progress: Progress) -> dict[str, Any]:
    res = []
    # single-regime bootstrap nodes: the regime DP is bang-bang (corner weights), which makes the slope degenerate
    base = ExperimentSpec(scenario=ScenarioSpec(generator="bootstrap", k_regimes=1, n_paths=600),
                          investor=InvestorSpec(start_age=45.0, retirement_age=65.0, max_age=100.0,
                                                initial_wealth=400_000.0),
                          policy=PolicySpec(type="dp"))
    u = C.universe(base)
    real = u.real_array()
    infl = u.inflation.to_numpy()
    for gi, g in enumerate(spec.gammas):
        progress("optimising", 0.05 + 0.4 * gi / len(spec.gammas))
        s = base.model_copy(update={"preferences": base.preferences.model_copy(update={"gamma": g})})
        prob, meta = build_problem(s)
        point = _slopes_at(policy_surfaces(grid_dp.solve(prob), meta, prob), spec.h1_ages)
        boots = []
        rng = np.random.default_rng(int(g * 100))
        resampler = StationaryBootstrap(real, infl, block_length=12.0)
        for b in range(spec.n_boot):
            r_b, i_b, _ = resampler.simulate(1, real.shape[0], rng, None)
            try:
                model = StationaryBootstrap(r_b[0], i_b[0], block_length=12.0)
                pb, mb = build_problem(s, model=model)
                boots.append(_slopes_at(policy_surfaces(grid_dp.solve(pb), mb, pb), spec.h1_ages))
            except Exception:
                continue
        arr = np.array(boots, dtype=float) if boots else np.full((0, len(spec.h1_ages)), np.nan)
        ci = []
        for j in range(len(spec.h1_ages)):
            col = arr[:, j][np.isfinite(arr[:, j])] if arr.size else np.array([])
            ci.append(np.quantile(col, [0.025, 0.975]).tolist() if len(col) >= 2 else None)
        res.append({"gamma": g, "ages": list(spec.h1_ages), "slope": point, "ci95": ci, "n_boot": len(boots)})
    contains_zero_all = True
    for r in res:
        for ci in r["ci95"]:
            if ci is None or not (ci[0] <= 1e-9 and ci[1] >= -1e-9):
                contains_zero_all = False
    return {"id": "H1", "statistic": "slope of optimal equity weight on q_t at fixed age (DP policy surfaces)",
            "benchmark": "age-only glidepath (zero slope)", "results": res, "falsified": bool(contains_zero_all),
            "rule": "falsified if every 95% parameter-bootstrap interval contains 0 across gamma in {2,4,6}"}


def test_h2(spec: HypothesesSpec) -> dict[str, Any]:
    if spec.sweep_id is None:
        return {"id": "H2", "status": "skipped", "reason": "no sweep_id"}
    res = registry.load_results(spec.sweep_id)
    if res is None:
        return {"id": "H2", "status": "skipped", "reason": "sweep has no results"}
    out = {}
    for b, m in res["matrices"].items():
        d = np.array(m["delta"], dtype=float)
        se = np.array(m["se"], dtype=float)
        ok = (d > 2 * se) & (d > spec.min_effect)
        out[b] = {"share_cells_supporting": float(ok.mean()), "mean_delta": float(np.nanmean(d)),
                  "falsified": bool(ok.mean() < 0.5)}
    return {"id": "H2", "statistic": "paired Delta_CE on common random numbers", "by_benchmark": out,
            "falsified": bool(all(v["falsified"] for v in out.values())),
            "rule": "falsified if Delta_CE < 2 SE or < 0.5% in a majority of cells"}


def test_h3_h4(spec: HypothesesSpec) -> list[dict[str, Any]]:
    if spec.attribution_id is None:
        return [{"id": "H3", "status": "skipped", "reason": "no attribution_id"},
                {"id": "H4", "status": "skipped", "reason": "no attribution_id"}]
    res = registry.load_results(spec.attribution_id)
    if res is None:
        return [{"id": "H3", "status": "skipped"}, {"id": "H4", "status": "skipped"}]
    regimes = [c for c in res["conditions"] if c["start_regime"] is not None]
    h3 = {}
    any_separated = False
    for k in res["sleeves"]:
        intervals = []
        for c in regimes:
            m = c["marginal"][k]
            intervals.append((c["condition"], m["mu_pct"] - 2 * m["se_pct"], m["mu_pct"] + 2 * m["se_pct"]))
        overlap = True
        for i in range(len(intervals)):
            for j in range(i + 1, len(intervals)):
                if intervals[i][2] < intervals[j][1] or intervals[j][2] < intervals[i][1]:
                    overlap = False
        if not overlap:
            any_separated = True
        h3[k] = {"intervals": intervals, "overlap": overlap}
    h4 = {}
    beats = False
    for c in res["conditions"]:
        for k in res["sleeves"]:
            m = c["marginal"][k]
            exceeds = m["mu_pct"] > 2 * m["se_pct"]
            h4.setdefault(k, []).append({"condition": c["condition"], "mu_pct": m["mu_pct"], "se_pct": m["se_pct"],
                                         "shapley": c["shapley"][k], "exceeds_band": bool(exceeds)})
            beats = beats or bool(exceeds)
    return [{"id": "H3", "statistic": "MU_k conditional on starting regime", "by_sleeve": h3,
             "falsified": not any_separated, "rule": "falsified if regime-conditional MU intervals overlap for all sleeves"},
            {"id": "H4", "statistic": "marginal / Shapley MU over sleeves vs two-asset universe", "by_sleeve": h4,
             "falsified": not beats, "rule": "falsified if no sleeve's MU exceeds its uncertainty band in any regime"}]


def run_hypotheses(spec: HypothesesSpec, progress: Progress) -> dict[str, Any]:
    out = [test_h1(spec, progress)]
    progress("summarising", 0.9)
    out.append(test_h2(spec))
    out.extend(test_h3_h4(spec))
    return {"hypotheses": out, "summary": {h["id"]: h.get("falsified") for h in out}, "timings": {}, "warnings": [
        "H1 uses the annual reduced-universe DP; bootstrap replications re-estimate the regime model"]}
