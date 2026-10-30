"""Compare two or more runs on common paths: paired Delta_CE and the divergent-path list."""
from collections.abc import Callable
from typing import Any

import numpy as np

from lifecycle.engine.lifecycle.simulator import evaluate
from lifecycle.engine.lifecycle.utility import path_ce
from lifecycle.runs import context as C
from lifecycle.runs import registry
from lifecycle.runs.policy_resolver import resolve
from lifecycle.runs.spec import CompareSpec, ExperimentSpec
from lifecycle.runs.summarize import SCALE, ce_block, delta_block, quantiles, shortfall_block

Progress = Callable[[str, float], None]


def run_compare(spec: CompareSpec, progress: Progress) -> dict[str, Any]:
    if len(spec.run_ids) < 2:
        raise ValueError("compare needs at least two run IDs")
    specs = []
    for rid in spec.run_ids:
        row = registry.get(rid)
        if row is None or row["kind"] != "experiment":
            raise ValueError("unknown experiment run: " + rid)
        specs.append(ExperimentSpec.model_validate(row["spec"]))
    base = specs[0]
    if any(s.policy.type == "dp" for s in specs):
        raise ValueError("DP runs are compared inside the DP experiment (annual reduced problem)")
    progress("generating_scenarios", 0.05)
    u = C.universe(base)
    ten = C.tensor(base)
    train_ten = ten if base.scenario.generator == "historical" else C.tensor(
        base, seed=C.train_seed(base), n_paths=min(base.scenario.n_train_paths, base.scenario.n_paths))
    T = int(round((base.investor.max_age - base.investor.start_age) * 12))
    ten = ten.head(T)
    train_ten = train_ten.head(T)
    ctx = C.build(base, ten, base.scenario.seed)
    train = C.build(base, train_ten, C.train_seed(base))
    outs = []
    labels = []
    for i, s in enumerate(specs):
        progress("simulating", 0.1 + 0.7 * i / len(specs))
        pol, info, sp = resolve(s.policy, ctx, train, C.spending(s), u)
        outs.append(evaluate(ctx, pol, sp))
        labels.append(pol.label + " [" + s.policy.spending_rule + " " + str(s.policy.withdrawal_rate) + "]")
    progress("summarising", 0.9)
    gamma = ctx.prefs.gamma
    ref = outs[0]
    policies = []
    for i in range(len(outs)):
        policies.append({"run_id": spec.run_ids[i], "label": labels[i], "ce": ce_block(outs[i], gamma),
                         "shortfall": shortfall_block(outs[i], ctx),
                         "delta_vs_first": delta_block(outs[i], ref, gamma) if i > 0 else None,
                         "fan_wealth": quantiles(outs[i].wealth_y, (0.05, 0.5, 0.95)),
                         "fan_consumption": quantiles(outs[i].cons_y, (0.05, 0.5, 0.95))})
    pairs = []
    for i in range(1, len(outs)):
        a = outs[0]
        b = outs[i]
        a_dep = a.deplete_month >= 0
        b_dep = b.deplete_month >= 0
        a_fail_b_ok = np.flatnonzero(a_dep & ~b_dep)
        b_fail_a_ok = np.flatnonzero(b_dep & ~a_dep)
        ce_a = path_ce(a.utility, gamma, a.sum_disc) * SCALE
        ce_b = path_ce(b.utility, gamma, b.sum_disc) * SCALE
        k = min(1500, len(ce_a))
        div = []
        for idx in list(a_fail_b_ok[: spec.n_divergent // 2]) + list(b_fail_a_ok[: spec.n_divergent // 2]):
            div.append({"path": int(idx), "a_depleted": bool(a_dep[idx]), "b_depleted": bool(b_dep[idx]),
                        "a_depletion_age": float(ctx.investor.start_age + a.deplete_month[idx] / 12) if a_dep[idx]
                        else None,
                        "b_depletion_age": float(ctx.investor.start_age + b.deplete_month[idx] / 12) if b_dep[idx]
                        else None,
                        "a_wealth": a.wealth_y[idx].tolist(), "b_wealth": b.wealth_y[idx].tolist(),
                        "a_consumption": a.cons_y[idx].tolist(), "b_consumption": b.cons_y[idx].tolist(),
                        "cum_real_equity_first_10y": float(np.prod(1 + ten.real_returns[idx, :120, 0]) - 1)})
        pairs.append({"a": spec.run_ids[0], "b": spec.run_ids[i], "delta_b_vs_a": delta_block(b, a, gamma),
                      "n_a_fails_b_survives": int(len(a_fail_b_ok)), "n_b_fails_a_survives": int(len(b_fail_a_ok)),
                      "share_b_better": float(np.mean(ce_b > ce_a)),
                      "scatter": {"a": ce_a[:k].tolist(), "b": ce_b[:k].tolist()}, "divergent": div})
    return {"ages": (ctx.investor.start_age + np.arange(ref.cons_y.shape[1] + 1)).tolist(), "policies": policies,
            "pairs": pairs, "common": {"universe": u.name, "generator": base.scenario.generator,
                                       "n_paths": ten.n_paths, "seed": base.scenario.seed},
            "summary": {"n_policies": len(outs)}, "timings": {}, "warnings": []}
