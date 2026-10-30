"""Validation for a run: Monte Carlo convergence, parameter- and model-uncertainty bands, cohort replay.

A result is reported as robust only if the sign of Delta_CE survives all three uncertainty sources.
"""
from collections.abc import Callable
from typing import Any

import numpy as np

from lifecycle.engine.lifecycle.simulator import evaluate
from lifecycle.engine.scenarios import fit_generator, generate
from lifecycle.engine.scenarios.bootstrap import StationaryBootstrap
from lifecycle.engine.scenarios.historical import HistoricalCohorts
from lifecycle.runs import context as C
from lifecycle.runs import registry
from lifecycle.runs.policy_resolver import benchmark_policy, resolve
from lifecycle.runs.spec import ExperimentSpec, ValidationSpec
from lifecycle.runs.summarize import ce_block, delta_block

Progress = Callable[[str, float], None]


def _fixed_policy(spec: ExperimentSpec):
    """Resolve the policy once (fit on seed-set A) and freeze it for all re-evaluations."""
    u = C.universe(spec)
    ten = C.tensor(spec)
    T = int(round((spec.investor.max_age - spec.investor.start_age) * 12))
    train_ten = ten if spec.scenario.generator == "historical" else C.tensor(
        spec, seed=C.train_seed(spec), n_paths=min(spec.scenario.n_train_paths, spec.scenario.n_paths))
    ctx = C.build(spec, ten.head(T), spec.scenario.seed)
    train = C.build(spec, train_ten.head(T), C.train_seed(spec))
    pol, info, sp = resolve(spec.policy, ctx, train, C.spending(spec), u)
    bench_name = spec.outputs.benchmark if spec.outputs.benchmark != "none" else "sixty_forty"
    bp, _ = benchmark_policy(bench_name, ctx, C.benchmark_spending(spec), train)
    return pol, sp, bp, C.benchmark_spending(spec), T, u


def _delta_on(spec: ExperimentSpec, ten, pol, sp, bp, bsp, seed: int) -> dict[str, float]:
    ctx = C.build(spec, ten, seed)
    a = evaluate(ctx, pol, sp)
    b = evaluate(ctx, bp, bsp)
    out = delta_block(a, b, ctx.prefs.gamma)
    out["ce"] = ce_block(a, ctx.prefs.gamma)["ce"]
    out["ce_benchmark"] = ce_block(b, ctx.prefs.gamma)["ce"]
    out["p_depletion"] = float(np.mean(a.deplete_month >= 0))
    out["p_depletion_benchmark"] = float(np.mean(b.deplete_month >= 0))
    return out


def run_validation(spec: ValidationSpec, progress: Progress) -> dict[str, Any]:
    row = registry.get(spec.run_id)
    if row is None or row["kind"] != "experiment":
        raise ValueError("unknown experiment run: " + spec.run_id)
    es = ExperimentSpec.model_validate(row["spec"])
    if es.policy.type == "dp":
        raise ValueError("validation of DP runs: use the grid-refinement check in the DP results")
    progress("generating_scenarios", 0.03)
    pol, sp, bp, bsp, T, u = _fixed_policy(es)
    out: dict[str, Any] = {"run_id": spec.run_id, "policy": pol.label, "benchmark": bp.label}

    # 1) Monte Carlo convergence on growing path counts (same generator, same seed)
    conv = []
    for i, n in enumerate(spec.path_counts):
        progress("simulating", 0.05 + 0.25 * i / max(len(spec.path_counts), 1))
        if es.scenario.generator == "historical":
            break
        s2 = es.model_copy(update={"scenario": es.scenario.model_copy(update={"n_paths": int(n)})})
        ten = C.tensor(s2).head(T)
        conv.append({"n_paths": int(n), **_delta_on(es, ten, pol, sp, bp, bsp, es.scenario.seed)})
    out["convergence"] = conv

    # 2) parameter uncertainty: re-estimate the scenario model on bootstrap resamples of history
    real = u.real_array()
    infl = u.inflation.to_numpy()
    rng = np.random.default_rng(es.scenario.seed + 3)
    resampler = StationaryBootstrap(real, infl, block_length=12.0)
    params = []
    gen = es.scenario.generator if es.scenario.generator != "historical" else "bootstrap"
    for b in range(spec.n_param_boot):
        progress("simulating", 0.3 + 0.35 * b / max(spec.n_param_boot, 1))
        r_b, i_b, _ = resampler.simulate(1, real.shape[0], rng, None)
        try:
            model = fit_generator(gen, r_b[0], i_b[0], u.assets, [], {"k_regimes": es.scenario.k_regimes,
                                                                     "block_length": es.scenario.block_length})
            ten = generate(model, u.assets, min(es.scenario.n_paths, 1000), T, es.scenario.seed)
            d = _delta_on(es, ten, pol, sp, bp, bsp, es.scenario.seed)
            params.append(d["delta"])
        except Exception as exc:  # a degenerate resample is recorded, not hidden
            params.append(None)
            out.setdefault("warnings", []).append("parameter replication %d failed: %s" % (b, exc))
    vals = np.array([p for p in params if p is not None], dtype=float)
    out["parameter_uncertainty"] = {"replications": params, "n": int(len(vals)),
                                    "quantiles": np.quantile(vals, [0.05, 0.25, 0.5, 0.75, 0.95]).tolist()
                                    if len(vals) > 0 else None,
                                    "share_positive": float(np.mean(vals > 0)) if len(vals) > 0 else None}

    # 3) model uncertainty: the same frozen policy under each generator in M
    models = []
    for i, g in enumerate(spec.generators):
        progress("simulating", 0.65 + 0.2 * i / max(len(spec.generators), 1))
        s2 = es.model_copy(update={"scenario": es.scenario.model_copy(update={"generator": g})})
        try:
            ten = C.tensor(s2).head(T)
            models.append({"generator": g, **_delta_on(es, ten, pol, sp, bp, bsp, es.scenario.seed)})
        except Exception as exc:
            models.append({"generator": g, "error": str(exc)})
    out["model_uncertainty"] = models

    # 4) historical cohort replay (overlapping cohorts are not independent)
    progress("summarising", 0.88)
    months_hist = real.shape[0]
    replay_T = min(T, int(spec.cohort_years * 12), months_hist - 12)
    dates = [d.date().isoformat() for d in u.real.index]
    cohorts = HistoricalCohorts(real, infl, dates)
    r_c, i_c, g_c = cohorts.simulate(0, replay_T, rng, None)
    from lifecycle.engine.scenarios.base import ScenarioTensor

    cten = ScenarioTensor(u.assets, r_c, i_c, g_c, 1, {"generator": "historical"})
    es_c = es.model_copy(update={"investor": es.investor.model_copy(
        update={"max_age": es.investor.start_age + replay_T / 12.0})})
    pol_c = pol.__class__(pol.wmode, pol.sched[:replay_T], pol.risky_w, pol.safe_w, pol.theta, pol.bucket_years,
                          pol.label)
    bp_c = bp.__class__(bp.wmode, bp.sched[:replay_T], bp.risky_w, bp.safe_w, bp.theta, bp.bucket_years, bp.label)
    ctx = C.build(es_c, cten, es.scenario.seed)
    a = evaluate(ctx, pol_c, sp)
    b = evaluate(ctx, bp_c, bsp)
    from lifecycle.engine.lifecycle.utility import path_ce

    pa = path_ce(a.utility, ctx.prefs.gamma, a.sum_disc) * 12000
    pb = path_ce(b.utility, ctx.prefs.gamma, b.sum_disc) * 12000
    starts = cohorts.last_starts
    step = max(1, len(starts) // 120)
    out["cohort_replay"] = {
        "horizon_years": replay_T / 12.0, "n_cohorts": len(starts),
        "caveat": "overlapping cohorts are not independent",
        "start": starts[::step], "ce_policy": pa[::step].tolist(), "ce_benchmark": pb[::step].tolist(),
        "depleted_policy": (a.deplete_month[::step] >= 0).tolist(),
        "depleted_benchmark": (b.deplete_month[::step] >= 0).tolist(),
        "share_policy_better": float(np.mean(pa > pb)),
        "p_depletion_policy": float(np.mean(a.deplete_month >= 0)),
        "p_depletion_benchmark": float(np.mean(b.deplete_month >= 0)),
        "delta_paired": delta_block(a, b, ctx.prefs.gamma),
    }

    # robustness verdict: sign must survive MC, parameter and model uncertainty
    signs = []
    if len(conv) > 0:
        last = conv[-1]
        signs.append(np.sign(last["delta"]) if abs(last["delta"]) > 2 * last["se"] else 0.0)
    if len(vals) > 0:
        q = np.quantile(vals, [0.05, 0.95])
        signs.append(np.sign(q[0]) if np.sign(q[0]) == np.sign(q[1]) else 0.0)
    ms = [m["delta"] for m in models if "delta" in m]
    if len(ms) > 0:
        signs.append(np.sign(ms[0]) if all(np.sign(x) == np.sign(ms[0]) and x != 0 for x in ms) else 0.0)
    robust = len(signs) > 0 and all(s != 0 for s in signs) and len(set(signs)) == 1
    out["robust"] = bool(robust)
    out["robust_sign"] = float(signs[0]) if robust else 0.0
    out["summary"] = {"robust": bool(robust), "run_id": spec.run_id}
    out["timings"] = {}
    out.setdefault("warnings", [])
    return out
