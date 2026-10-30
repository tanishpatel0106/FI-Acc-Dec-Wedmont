"""Sweeps (heatmaps): a grid of experiment cells sharing one scenario tensor (common random numbers).

Decumulation surface: withdrawal rate x years relative to retirement.
Accumulation surface: savings rate x starting age.
Every cell is persisted as its own experiment run (drill-down by run ID); each cell stores the
paired Delta_CE against every benchmark so switching the benchmark is a lookup, not a recompute.
"""
from collections.abc import Callable
from typing import Any

import numpy as np

from lifecycle.config import engine_version, lockfile_hash
from lifecycle.engine.lifecycle.simulator import evaluate
from lifecycle.runs import context as C
from lifecycle.runs import registry
from lifecycle.runs.hashing import canonical_json, run_id_for, spec_hash
from lifecycle.runs.policy_resolver import benchmark_policy, resolve
from lifecycle.runs.spec import ExperimentSpec, SweepSpec
from lifecycle.runs.summarize import delta_block, run_payload

Progress = Callable[[str, float], None]


def wealth_multiple(years_to_retirement: float) -> float:
    """Rule-of-thumb wealth/income multiple used to seed pre-retirement cells."""
    return float(np.interp(years_to_retirement, [0, 10, 25, 35, 45], [10.0, 6.0, 3.0, 1.0, 0.2]))


def cell_specs(sweep: SweepSpec) -> tuple[list[list[ExperimentSpec]], list[float], list[float], str, str]:
    base = sweep.base
    inv = base.investor
    cells: list[list[ExperimentSpec]] = []
    if sweep.kind == "decumulation":
        xs = list(sweep.withdrawal_rates)
        ys = list(sweep.years_relative)
        starts = [inv.retirement_age + y for y in ys]
    else:
        xs = list(sweep.savings_rates)
        ys = list(sweep.start_ages)
        starts = list(ys)
    horizon = int(round((inv.max_age - min(starts)) * 12))
    for yi, y in enumerate(ys):
        row = []
        start_age = starts[yi]
        to_ret = inv.retirement_age - start_age
        for x in xs:
            i_upd: dict[str, Any] = {"start_age": float(start_age)}
            p_upd: dict[str, Any] = {"type": sweep.optimizer}
            if to_ret > 0:
                i_upd["initial_wealth"] = float(round(wealth_multiple(to_ret) * inv.income, 2))
            if sweep.kind == "decumulation":
                p_upd["withdrawal_rate"] = float(x)
            else:
                i_upd["savings_rate"] = float(x)
            spec = base.model_copy(update={
                "investor": inv.model_copy(update=i_upd),
                "policy": base.policy.model_copy(update=p_upd),
                "scenario": base.scenario.model_copy(update={"horizon_months": horizon}),
                "outputs": base.outputs.model_copy(update={"benchmark": sweep.benchmarks[0]}),
            })
            row.append(spec)
        cells.append(row)
    if sweep.kind == "decumulation":
        return cells, xs, ys, "withdrawal rate", "years relative to retirement"
    return cells, xs, ys, "savings rate", "starting age"


def evaluate_cell(spec: ExperimentSpec, benchmarks: tuple[str, ...]) -> dict[str, Any]:
    u = C.universe(spec)
    ten = C.tensor(spec)
    n_train = min(spec.scenario.n_train_paths, spec.scenario.n_paths)
    train_ten = ten if spec.scenario.generator == "historical" else C.tensor(spec, seed=C.train_seed(spec),
                                                                              n_paths=n_train)
    T = int(round((spec.investor.max_age - spec.investor.start_age) * 12))
    ten = ten.head(T)
    train_ten = train_ten.head(T)
    ctx = C.build(spec, ten, spec.scenario.seed)
    train = C.build(spec, train_ten, C.train_seed(spec))
    sp = C.spending(spec)
    policy, info, sp_pol = resolve(spec.policy, ctx, train, sp, u)
    out = evaluate(ctx, policy, sp_pol)
    bench_outs = {}
    bench_info = {}
    bsp = C.benchmark_spending(spec)
    for b in benchmarks:
        bp, binfo = benchmark_policy(b, ctx, bsp, train)
        bench_outs[b] = evaluate(ctx, bp, bsp)
        bench_info[b] = {"label": bp.label, **{k: v for k, v in binfo.items() if k != "grid"}}
    first = benchmarks[0]
    payload = run_payload(ctx, out, bench_outs[first], spec.outputs.quantiles, spec.outputs.n_sample_paths)
    payload["policy"] = {"label": policy.label, **info}
    payload["benchmark"] = {"name": first, **bench_info[first]}
    payload["benchmarks"] = {b: {**delta_block(out, bench_outs[b], ctx.prefs.gamma), **bench_info[b]}
                             for b in benchmarks}
    payload["universe"] = {"name": u.name, "assets": list(u.assets),
                           "window": [u.start.date().isoformat(), u.end.date().isoformat()]}
    payload["scenario"] = ten.meta
    payload["mean_weights_at_start"] = dict(zip(u.assets, out.weights_y[:, 0].mean(axis=0).tolist()))
    return payload


def run_sweep(sweep: SweepSpec, progress: Progress, sweep_id: str) -> dict[str, Any]:
    from lifecycle.runs.executor import meta_for, summary_of, with_catalog

    cells, xs, ys, xlab, ylab = cell_specs(sweep)
    n_cells = len(xs) * len(ys)
    progress("generating_scenarios", 0.02)
    grid: list[list[dict[str, Any]]] = []
    k = 0
    for yi in range(len(ys)):
        row = []
        for xi in range(len(xs)):
            spec = with_catalog(cells[yi][xi])
            rid = run_id_for("experiment", spec)
            existing = registry.get(rid)
            res = registry.load_results(rid) if existing is not None and existing["status"] == "done" else None
            if res is None or "benchmarks" not in res:
                if existing is None:
                    registry.create(rid, "experiment", canonical_json(spec), spec_hash(spec), spec.data.catalog_hash,
                                    engine_version(), lockfile_hash(), None, sweep_id)
                registry.update(rid, status="running", stage="simulating", started_at=registry.now(),
                                parent_id=sweep_id)
                try:
                    res = evaluate_cell(spec, sweep.benchmarks)
                except Exception as exc:
                    registry.update(rid, status="failed", stage="failed", error=str(exc))
                    raise
                res["meta"] = meta_for(rid)
                registry.save_results(rid, res)
                registry.update(rid, status="done", stage="done", progress=1.0, finished_at=registry.now(),
                                summary=summary_of("experiment", res))
            cell = {"run_id": rid, "x": xs[xi], "y": ys[yi], "ce": res["ce"]["policy"]["ce"],
                    "ce_se": res["ce"]["policy"]["se"], "policy": res["policy"].get("label"),
                    "theta": res["policy"].get("theta"), "p_depletion": res["shortfall"]["p_depletion"],
                    "p_depletion_benchmark": res.get("benchmark_shortfall", {}).get("p_depletion"),
                    "benchmarks": res["benchmarks"], "weights": res.get("mean_weights_at_start")}
            row.append(cell)
            k += 1
            progress("optimising", 0.05 + 0.9 * k / n_cells)
        grid.append(row)
    progress("summarising", 0.97)
    matrices = {}
    for b in sweep.benchmarks:
        d = [[c["benchmarks"][b]["delta"] for c in row] for row in grid]
        s = [[c["benchmarks"][b]["se"] for c in row] for row in grid]
        matrices[b] = {"delta": d, "se": s}
    first = sweep.benchmarks[0]
    dm = np.array(matrices[first]["delta"], dtype=float)
    sm = np.array(matrices[first]["se"], dtype=float)
    best = np.unravel_index(np.nanargmax(dm), dm.shape)
    summary = {"kind": sweep.kind, "universe": sweep.base.data.universe, "generator": sweep.base.scenario.generator,
               "gamma": sweep.base.preferences.gamma, "optimizer": sweep.optimizer, "benchmark": first,
               "mean_delta": float(np.nanmean(dm)), "max_delta": float(dm[best]),
               "max_cell": {"x": xs[best[1]], "y": ys[best[0]]},
               "share_significant": float(np.mean(np.abs(dm) > 2 * sm)), "n_cells": n_cells}
    return {"kind": sweep.kind, "x": xs, "y": ys, "x_label": xlab, "y_label": ylab, "cells": grid,
            "matrices": matrices, "shortfall": [[c["p_depletion"] for c in row] for row in grid],
            "shortfall_benchmark": [[c["p_depletion_benchmark"] for c in row] for row in grid],
            "benchmarks": list(sweep.benchmarks), "summary": summary, "timings": {}, "warnings": []}
