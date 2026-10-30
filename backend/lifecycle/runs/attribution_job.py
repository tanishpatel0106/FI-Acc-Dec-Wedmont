"""Marginal and Shapley asset-class utility (M6), unconditional and by starting regime (H3/H4).

CE*(S) is the CE of the static CRRA-optimal constant mix restricted to sleeves S, fitted on
seed-set A and evaluated on seed-set B with common random numbers.
"""
from collections.abc import Callable
from typing import Any

import numpy as np

from lifecycle.engine import attribution
from lifecycle.engine.lifecycle import policies as pol
from lifecycle.engine.lifecycle.simulator import ce_annual, evaluate
from lifecycle.engine.lifecycle.utility import paired_delta_ce
from lifecycle.engine.optimize import static
from lifecycle.runs import context as C
from lifecycle.runs import registry
from lifecycle.runs.spec import AttributionSpec, ExperimentSpec, SweepSpec

Progress = Callable[[str, float], None]


def _base_spec(spec: AttributionSpec) -> ExperimentSpec:
    row = registry.get(spec.sweep_id)
    if row is None:
        raise ValueError("unknown sweep: " + spec.sweep_id)
    if row["kind"] == "sweep":
        base = SweepSpec.model_validate(row["spec"]).base
    else:
        base = ExperimentSpec.model_validate(row["spec"])
    gen = base.scenario.generator if base.scenario.generator != "historical" else "bootstrap"
    return base.model_copy(update={
        "data": base.data.model_copy(update={"universe": spec.universe}),
        "scenario": base.scenario.model_copy(update={"n_paths": spec.n_paths, "horizon_months": None,
                                                     "generator": gen}),
        "investor": base.investor.model_copy(update={"start_age": base.investor.retirement_age}),
        "policy": base.policy.model_copy(update={"type": "utility_static"})})


def _ce_star_factory(spec_e: ExperimentSpec, start_regime: int | None, cache: dict, store: dict):
    T = int(round((spec_e.investor.max_age - spec_e.investor.start_age) * 12))
    ten = C.tensor(spec_e, start_regime=start_regime).head(T)
    tr = C.tensor(spec_e, seed=C.train_seed(spec_e), n_paths=min(600,
                                                                  spec_e.scenario.n_paths),
                  start_regime=start_regime).head(T)
    sp = C.spending(spec_e)
    gamma = spec_e.preferences.gamma

    def ce_star(subset: tuple[str, ...]) -> float:
        key = tuple(sorted(subset))
        if key in cache:
            return cache[key]
        sub = [a for a in ten.assets if a in key]
        t_sub = ten.select_assets(sub)
        tr_sub = tr.select_assets(sub)
        ctx = C.build(spec_e, t_sub, spec_e.scenario.seed)
        trc = C.build(spec_e, tr_sub, C.train_seed(spec_e))

        def obj(w: np.ndarray) -> float:
            return ce_annual(evaluate(trc, pol.constant_mix(w, trc.months), sp), gamma)[0]

        n = len(sub)
        if n == 1:
            w = np.ones(1)
        else:
            w, _ = static.maximize_objective(obj, n, maxiter=20, step=0.03)
        out = evaluate(ctx, pol.constant_mix(w, ctx.months), sp)
        ce, _ = ce_annual(out, gamma)
        cache[key] = ce
        store[key] = {"weights": dict(zip(sub, w.tolist())), "utility": out.utility, "sum_disc": out.sum_disc}
        return ce

    return ce_star


def run_attribution(spec: AttributionSpec, progress: Progress) -> dict[str, Any]:
    spec_e = _base_spec(spec)
    u = C.universe(spec_e)
    base = tuple(a for a in spec.base if a in u.assets)
    if spec.sleeves is None:
        pref = ["tbill", "tips", "ig_credit", "intl_eq", "em_eq", "reit", "gold"]
        sleeves = tuple(a for a in pref if a in u.assets and a not in base)[:6]
    else:
        sleeves = tuple(a for a in spec.sleeves if a in u.assets and a not in base)
    gamma = spec_e.preferences.gamma
    results: dict[str, Any] = {"base": list(base), "sleeves": list(sleeves), "universe": u.name,
                               "window": [u.start.date().isoformat(), u.end.date().isoformat()]}
    conditions: list[tuple[str, int | None, ExperimentSpec]] = [("unconditional", None, spec_e)]
    if spec.by_regime:
        ms_spec = spec_e.model_copy(update={"scenario": spec_e.scenario.model_copy(
            update={"generator": "markov_switching"})})
        model = C.fitted_model(ms_spec)
        for s in range(model.k):
            conditions.append(("regime %d: %s" % (s, model.regime_names()[s]), s, ms_spec))
    blocks = []
    for ci, (name, sr, sp_e) in enumerate(conditions):
        progress("optimising", 0.05 + 0.9 * ci / len(conditions))
        cache: dict = {}
        store: dict = {}
        ce_star = _ce_star_factory(sp_e, sr, cache, store)
        phi, values = attribution.shapley(base, sleeves, ce_star)

        def skey(subset: tuple[str, ...]) -> tuple[str, ...]:
            return tuple(sorted(tuple(base) + tuple(subset)))

        ce_b = values[()]
        marginal = {}
        for k in sleeves:
            u_with = store[skey((k,))]["utility"]
            u_base = store[skey(())]["utility"]
            d, se = paired_delta_ce(u_with, u_base, gamma, store[skey(())]["sum_disc"])
            marginal[k] = {"mu": values[(k,)] - ce_b, "mu_pct": d, "se_pct": se, "se": se * ce_b}
        full = tuple(sorted(sleeves))
        blocks.append({"condition": name, "start_regime": sr, "ce_base": ce_b, "ce_full": values[full],
                       "marginal": marginal, "shapley": phi,
                       "weights_full": store[skey(full)]["weights"], "weights_base": store[skey(())]["weights"],
                       "n_subsets": len(values)})
    results["conditions"] = blocks
    results["summary"] = {"sleeves": list(sleeves), "n_conditions": len(blocks),
                          "top_sleeve": max(blocks[0]["shapley"], key=lambda k: blocks[0]["shapley"][k])
                          if sleeves else None}
    results["timings"] = {}
    results["warnings"] = ["CE*(S) uses static CRRA-optimal constant mixes; SE from paired path utilities"]
    return results
