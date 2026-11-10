"""E29 / MS-07, MS-10: as-of conditional versus unconditional scenarios on the same calibration window.

Conditional = Markov-switching paths started from the filtered regime probability at the as-of date
(information through that month only). Unconditional = the same fitted model started from its stationary
distribution. Both share calibration window, seeds and policies; only the initial state differs.
"""
from typing import Any

import numpy as np
from pydantic import Field

from lifecycle.engine.scenarios.base import generate
from lifecycle.runs import context as C
from lifecycle.studies import common as S
from lifecycle.studies.frontier import solve_bmin


class AsOfSpec(S.Frozen):
    data: S.StudyData = Field(default_factory=lambda: S.StudyData(universe="core_long_history"))
    scenario: S.StudyScenario = Field(default_factory=lambda: S.StudyScenario(generator="markov_switching",
                                                                              n_paths=2000))
    investor: S.StudyInvestor = Field(default_factory=lambda: S.StudyInvestor(horizon_years=30))
    preferences: S.StudyPrefs = Field(default_factory=S.StudyPrefs)
    as_of: str | None = None          # calibration_end; None = latest panel month
    r_grid: tuple[float, ...] = (0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.06)
    b_grid: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    target: float = 0.90
    label: str | None = None


def run_asof(spec: AsOfSpec, progress: S.Progress) -> dict[str, Any]:
    data = spec.data.model_copy(update={"calibration_end": spec.as_of}) if spec.as_of else spec.data
    u = S.universe_or_raise(data)
    es = S.experiment_spec(data, spec.scenario, spec.investor, spec.preferences, generator="markov_switching")
    progress("fitting", 0.05)
    model = C.fitted_model(es)
    T = spec.investor.horizon_years * 12
    p_cond = model.filtered[-1] @ model.P
    tens = {}
    for name, p0 in (("conditional", p_cond), ("unconditional", model.stationary)):
        saved = model.filtered[-1].copy()
        # the generator draws its first state from filtered[-1] @ P; impose the chosen start distribution
        try:
            target = np.linalg.solve(model.P.T, p0)
            target = np.clip(target, 0, None)
            target /= target.sum()
            model.filtered[-1] = target
            ten = generate(model, u.assets, spec.scenario.n_paths, T, spec.scenario.seed, None)
        finally:
            model.filtered[-1] = saved
        from lifecycle.engine.scenarios.pit_signals import decision_regime

        ten.decision, sig = decision_regime(ten, model)
        ten.meta["decision_signal"] = sig
        tens[name] = ten
    ctx = S.get_context(es, tens["conditional"], es.scenario.seed)
    assets = u.assets
    mh = T
    out: dict[str, Any] = {"fans": {}, "surface": {}, "thresholds": {}}
    progress("simulating", 0.3)
    for name, ten in tens.items():
        w = S.weights_vector({"us_eq": 0.6, "ust_10y": 0.4}, assets)
        o = S.run(ctx, w, S.strategy("calendar_12m"), rate=0.04, record=True, tensor=ten)
        out["fans"][name] = {"wealth": S.fan(o.wealth_y), "consumption": S.fan(o.cons_y),
                             "success": S.success_block(o.first_shortfall, mh), "ce": S.ce_of(o, spec.preferences.gamma)}
        P = np.zeros((len(spec.b_grid), len(spec.r_grid)))
        for bi, b in enumerate(spec.b_grid):
            wb = S.weights_vector({"us_eq": 1 - b, "ust_10y": b} if b < 1 else {"ust_10y": 1.0}, assets)
            for ri, r in enumerate(spec.r_grid):
                ob = S.run(ctx, wb, S.strategy("calendar_12m"), rate=r, tensor=ten)
                P[bi, ri] = S.success(ob.first_shortfall, mh).mean()
        out["surface"][name] = S.to_list(P)
        out["thresholds"][name] = [dict(r=r, **solve_bmin(P[:, i], list(spec.b_grid), spec.target))
                                   for i, r in enumerate(spec.r_grid)]
    d = np.array(out["surface"]["conditional"]) - np.array(out["surface"]["unconditional"])
    se = np.sqrt(2 * 0.25 / spec.scenario.n_paths)
    return {"kind": "asof", "as_of": u.end.date().isoformat(), "universe": S.universe_block(u),
            "start_probabilities": {"conditional": p_cond.tolist(), "unconditional": model.stationary.tolist()},
            "regime_names": model.regime_names(), "r": list(spec.r_grid), "b": list(spec.b_grid), "target": spec.target,
            **out, "delta_surface": S.to_list(d), "delta_flag": (np.abs(d) > 2 * se).astype(int).tolist(),
            "model_uncertainty_note": "the delta isolates the effect of the observed starting state; parameter and "
                                      "model uncertainty are not included (see Withdrawal Lab robustness)",
            "warnings": S.common_warnings(u, tens["conditional"]) + [
                "conditional paths are model-generated scenarios, not forecasts"], "timings": {},
            "summary": {"as_of": u.end.date().isoformat()}}
