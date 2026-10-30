"""Single-experiment pipeline: scenarios -> simulation -> (optimisation) -> summary."""
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from lifecycle.data import panel
from lifecycle.engine.lifecycle.simulator import evaluate
from lifecycle.runs import context as C
from lifecycle.runs.policy_resolver import benchmark_policy, resolve
from lifecycle.runs.spec import ExperimentSpec
from lifecycle.runs.summarize import run_payload

Progress = Callable[[str, float], None]


def _noop(stage: str, frac: float) -> None:
    return None


def run_experiment(spec: ExperimentSpec, progress: Progress = _noop) -> dict[str, Any]:
    if spec.policy.type == "dp":
        from lifecycle.runs.dp_job import run_dp

        return run_dp(spec, progress)
    timings: dict[str, float] = {}
    warnings: list[str] = []
    t0 = time.time()
    progress("generating_scenarios", 0.05)
    u = C.universe(spec)
    ten = C.tensor(spec)
    n_train = min(spec.scenario.n_train_paths, spec.scenario.n_paths)
    if spec.scenario.generator == "historical":
        train_ten = ten  # cohorts are deterministic; fitting and reporting share the history
        warnings.append("historical cohorts: policy fitted and reported on the same overlapping cohorts")
    else:
        train_ten = C.tensor(spec, seed=C.train_seed(spec), n_paths=n_train)
    timings["scenarios"] = time.time() - t0

    t1 = time.time()
    progress("simulating", 0.25)
    ctx = C.build(spec, ten, spec.scenario.seed)
    train = C.build(spec, train_ten, C.train_seed(spec))
    spending = C.spending(spec)
    policy, info, spending = resolve(spec.policy, ctx, train, spending, u, progress)
    progress("simulating", 0.6)
    out = evaluate(ctx, policy, spending)
    bench_out = None
    bench_info: dict[str, Any] = {}
    if spec.outputs.benchmark != "none":
        bp, bench_info = benchmark_policy(spec.outputs.benchmark, ctx, C.benchmark_spending(spec), train)
        bench_info["label"] = bp.label
        bench_out = evaluate(ctx, bp, C.benchmark_spending(spec))
    timings["simulation"] = time.time() - t1

    progress("summarising", 0.85)
    payload = run_payload(ctx, out, bench_out, spec.outputs.quantiles, spec.outputs.n_sample_paths)
    payload["policy"] = {"label": policy.label, **info}
    payload["benchmark"] = {"name": spec.outputs.benchmark, **bench_info}
    payload["scenario"] = ten.meta
    payload["universe"] = {"name": u.name, "assets": list(u.assets), "window": [u.start.date().isoformat(),
                                                                              u.end.date().isoformat()],
                           "excluded": u.excluded, "dropped_months": u.n_dropped_months,
                           "provenance": _provenance(u.assets)}
    payload["mortality_source"] = C.life_table_provenance()
    if "model_generated" in payload["universe"]["provenance"].values():
        warnings.append("some return series are model-generated from public yields (no WRDS data)")
    if panel.synthetic_mode():
        warnings.append("SYNTHETIC DATA: results are for testing only")
    if spec.outputs.persist_paths:
        from lifecycle.runs.registry import run_folder

        np.savez_compressed(run_folder(_rid(spec)) / "paths.npz", utility=out.utility,
                            wealth=out.wealth_y, consumption=out.cons_y,
                            bench_utility=bench_out.utility if bench_out is not None else np.zeros(0))
    timings["total"] = time.time() - t0
    payload["timings"] = timings
    payload["warnings"] = warnings
    return payload


def _rid(spec: ExperimentSpec) -> str:
    from lifecycle.runs.hashing import run_id_for

    return run_id_for("experiment", spec)


def _provenance(assets: tuple[str, ...]) -> dict[str, str]:
    cat = panel.catalog()
    out = {}
    for a in assets:
        rows = cat[cat["series_id"] == a]
        out[a] = str(rows["provenance"].iloc[0]) if len(rows) > 0 else "unknown"
    return out


def sample_paths(spec: ExperimentSpec, n: int = 200) -> dict[str, np.ndarray]:
    """Re-simulate (deterministically) and return a sample of path arrays for the Arrow endpoint."""
    u = C.universe(spec)
    ten = C.tensor(spec)
    train_ten = ten if spec.scenario.generator == "historical" else C.tensor(
        spec, seed=C.train_seed(spec), n_paths=min(spec.scenario.n_train_paths, spec.scenario.n_paths))
    ctx = C.build(spec, ten, spec.scenario.seed)
    train = C.build(spec, train_ten, C.train_seed(spec))
    policy, _, spending = resolve(spec.policy, ctx, train, C.spending(spec), u)
    out = evaluate(ctx, policy, spending)
    k = min(n, out.utility.shape[0])
    result = {"wealth": out.wealth_y[:k], "consumption": out.cons_y[:k]}
    if spec.outputs.benchmark != "none":
        bp, _ = benchmark_policy(spec.outputs.benchmark, ctx, C.benchmark_spending(spec), train)
        b = evaluate(ctx, bp, C.benchmark_spending(spec))
        result["bench_wealth"] = b.wealth_y[:k]
        result["bench_consumption"] = b.cons_y[:k]
    return result
