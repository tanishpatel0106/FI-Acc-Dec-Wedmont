"""E04/E05 / F2: optimal bond share over a planned signed net-flow rate q x age (brief 2.5).

q is an *exogenous planned* annual net draw as a share of reference wealth W_ref (negative = net
contribution), held fixed over the cell's horizon min(H, 95 - age). It is never inferred from realised
wealth, so the denominator cannot drift with outcomes. Age enters this surface only through the
remaining horizon and the survival curve (no human-capital channel; the lifecycle persona below adds
labour income explicitly).

Objectives per cell, on training paths (seed-set A) with evaluation on disjoint test paths (seed-set B):
  CE      CRRA certainty equivalent of total real resources delivered = terminal wealth + funded draws
  survival P(no unmet planned draw over the horizon)
"""
from typing import Any

import numpy as np
from pydantic import Field

from lifecycle.data import panel
from lifecycle.engine.lifecycle import ledger
from lifecycle.engine.lifecycle.policies import target_date_equity
from lifecycle.studies import common as S

DEFAULT_Q = (-0.15, -0.10, -0.075, -0.05, -0.03, -0.02, -0.01, -0.005, 0.0, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05,
             0.06, 0.07, 0.08, 0.10)


class SignedFlowSpec(S.Frozen):
    data: S.StudyData = Field(default_factory=lambda: S.StudyData(universe="core_long_history"))
    scenario: S.StudyScenario = Field(default_factory=lambda: S.StudyScenario(n_paths=1500, n_train_paths=1000))
    preferences: S.StudyPrefs = Field(default_factory=S.StudyPrefs)
    costs: S.StudyCosts = Field(default_factory=S.StudyCosts)
    q_grid: tuple[float, ...] = DEFAULT_Q
    ages: tuple[float, ...] = (25, 35, 45, 55, 65, 75, 85)
    horizon_years: int = Field(20, ge=5, le=40)
    b_step: float = Field(0.1, gt=0, le=0.5)
    w_ref: float = 1_000_000.0
    equity: str = "us_eq"
    bond: str = "ust_10y"
    rebalancer: str = "calendar_12m"
    n_boot: int = Field(100, ge=0, le=500)
    real_discount_rate: float | None = None   # None -> latest GSW TIPS 10Y real zero (or 1.5% if unavailable)
    persona_income: float = 100_000.0
    persona_savings: tuple[float, ...] = (0.05, 0.10, 0.15, 0.20, 0.25)
    persona_start_ages: tuple[float, ...] = (25, 30, 35, 40, 45, 50)
    persona_target_multiple: float = 12.0
    label: str | None = None


def _w(assets, eq, bd, b):
    w = np.zeros(len(assets))
    w[assets.index(eq)] += 1 - b
    w[assets.index(bd)] += b
    return w


def _real_rate(spec: SignedFlowSpec) -> tuple[float, str]:
    if spec.real_discount_rate is not None:
        return spec.real_discount_rate, "user-specified"
    try:
        s = panel.series("gsw_real_10").dropna()
        return float(s.iloc[-1]), "GSW TIPS 10Y real zero, " + s.index[-1].date().isoformat()
    except KeyError:
        return 0.015, "fallback 1.5% (no real curve in panel)"


def run_signed_flow(spec: SignedFlowSpec, progress: S.Progress) -> dict[str, Any]:
    u = S.universe_or_raise(spec.data)
    if spec.bond not in u.assets:
        raise S.IncompatibleUniverse("bond %s not in universe %s" % (spec.bond, u.name))
    bs = [round(i * spec.b_step, 6) for i in range(int(round(1 / spec.b_step)) + 1)]
    qs = list(spec.q_grid)
    ages = list(spec.ages)
    tr = S.strategy(spec.rebalancer, spec.costs)
    gamma = spec.preferences.gamma
    nA, nQ, nB = len(ages), len(qs), len(bs)
    CE_tr = np.zeros((nA, nQ, nB))
    CE_te = np.zeros((nA, nQ, nB))
    SV_tr = np.zeros((nA, nQ, nB))
    SV_te = np.zeros((nA, nQ, nB))
    res_paths: dict[tuple[int, int, int], np.ndarray] = {}
    surv_paths: dict[tuple[int, int, int], np.ndarray] = {}
    horizons = []
    k = 0
    progress("generating_scenarios", 0.02)
    for ai, age in enumerate(ages):
        h = int(min(spec.horizon_years, 95 - age))
        horizons.append(h)
        inv = S.StudyInvestor(age=age, retirement_age=min(max(age, 40), 80), horizon_years=h,
                              initial_wealth=spec.w_ref, mortality=True)
        es, ctx, train = S.train_test(spec.data, spec.scenario, inv, spec.preferences)
        assets = ctx.tensor.assets
        for qi, q in enumerate(qs):
            for bi, b in enumerate(bs):
                w = _w(assets, spec.equity, spec.bond, b)
                o_tr = S.run(train, w, tr, spend="signed", q=q, w_ref=spec.w_ref, zero_income=True)
                o_te = S.run(ctx, w, tr, spend="signed", q=q, w_ref=spec.w_ref, zero_income=True)
                CE_tr[ai, qi, bi] = S.resources_ce(o_tr.terminal, o_tr.funded, gamma)
                CE_te[ai, qi, bi] = S.resources_ce(o_te.terminal, o_te.funded, gamma)
                SV_tr[ai, qi, bi] = float((o_tr.first_shortfall < 0).mean())
                SV_te[ai, qi, bi] = float((o_te.first_shortfall < 0).mean())
                res_paths[(ai, qi, bi)] = np.maximum(o_tr.terminal + o_tr.funded, 1000.0) / 1e6
                surv_paths[(ai, qi, bi)] = o_tr.first_shortfall < 0
                k += 1
                if k % 40 == 0:
                    progress("optimising", 0.05 + 0.55 * k / (nA * nQ * nB))
    # optimal shares on training paths, ties broken toward fewer bonds
    b_ce = np.array([[bs[int(np.argmax(CE_tr[a, q]))] for q in range(nQ)] for a in range(nA)])
    b_sv = np.array([[bs[int(np.argmax(SV_tr[a, q] - 1e-9 * np.arange(nB)))] for q in range(nQ)] for a in range(nA)])
    b_ce_test = np.array([[bs[int(np.argmax(CE_te[a, q]))] for q in range(nQ)] for a in range(nA)])
    # restricted policies fitted on training paths: age-only and q-only (normalised CE)
    rel = CE_tr / CE_tr.max(axis=2, keepdims=True)
    b_age = [bs[int(np.argmax(rel[a].sum(axis=0)))] for a in range(nA)]
    b_q = [bs[int(np.argmax(rel[:, q].sum(axis=0)))] for q in range(nQ)]
    td = [float(1 - target_date_equity(np.array([a]))[0]) for a in ages]
    full_ce = np.array([[CE_te[a, q, bs.index(b_ce[a, q])] for q in range(nQ)] for a in range(nA)])

    def oos(pick):
        return np.array([[CE_te[a, q, bs.index(pick(a, q))] / full_ce[a, q] - 1 for q in range(nQ)] for a in range(nA)])

    nearest = lambda x: min(bs, key=lambda v: abs(v - x))  # noqa: E731
    d_age = oos(lambda a, q: b_age[a])
    d_q = oos(lambda a, q: b_q[q])
    d_td = oos(lambda a, q: nearest(td[a]))
    # marginal slopes d b*/d q at fixed age: OLS over the q grid, path-bootstrap CI
    progress("uncertainty", 0.65)
    qa = np.array(qs)

    def slope(bv):
        x = qa - qa.mean()
        return float(np.sum(x * (bv - bv.mean())) / np.sum(x * x))

    def local_slope(bv):
        i0 = int(np.argmin(np.abs(qa)))
        lo, hi = max(i0 - 2, 0), min(i0 + 2, nQ - 1)
        return float((bv[hi] - bv[lo]) / (qa[hi] - qa[lo]))

    slopes = []
    rng = np.random.default_rng(spec.scenario.seed + 5)
    Ntr = next(iter(res_paths.values())).shape[0]
    boot_idx = [rng.integers(0, Ntr, Ntr) for _ in range(spec.n_boot)]
    for ai, age in enumerate(ages):
        bv = b_ce[ai].astype(float)
        sb, lb = [], []
        for idx in boot_idx:
            ce = np.zeros((nQ, nB))
            for qi in range(nQ):
                for bi in range(nB):
                    r = res_paths[(ai, qi, bi)][idx]
                    ce[qi, bi] = np.mean(r ** (1 - gamma)) ** (1 / (1 - gamma)) if gamma != 1 else np.exp(np.mean(np.log(r)))
            bb = np.array([bs[int(np.argmax(ce[qi]))] for qi in range(nQ)], dtype=float)
            sb.append(slope(bb))
            lb.append(local_slope(bb))
        slopes.append({"age": age, "slope": slope(bv), "lo": float(np.quantile(sb, 0.025)) if sb else None,
                       "hi": float(np.quantile(sb, 0.975)) if sb else None, "local_slope_at_zero": local_slope(bv),
                       "local_lo": float(np.quantile(lb, 0.025)) if lb else None,
                       "local_hi": float(np.quantile(lb, 0.975)) if lb else None,
                       "units": "change in optimal bond share per unit of q (per 100% of W_ref per year)"})
    # funded ratio W_ref / PV(planned net draws) on a real curve with mortality (LC-05)
    rr, rr_src = _real_rate(spec)
    from lifecycle.engine.lifecycle import mortality
    from lifecycle.runs import context as C

    qv = mortality.q_vector(C.load_life_table(), "unisex")
    funded_ratio = np.full((nA, nQ), np.nan)
    for ai, age in enumerate(ages):
        Ssv = mortality.monthly_survival(qv, age, horizons[ai] * 12)[::12][1:]
        disc = (1 + rr) ** -np.arange(1, horizons[ai] + 1)
        for qi, q in enumerate(qs):
            if q > 0:
                pv = float(np.sum(q * spec.w_ref * Ssv * disc))
                funded_ratio[ai, qi] = spec.w_ref / pv
    # lifecycle persona (LC-04, LC-06, LC-07, LC-08): CGM income, saving, retirement at 65, 4% fixed real draw
    progress("persona", 0.8)
    persona = _persona(spec, u, b_ce, ages, qs, bs, tr)
    return {
        "kind": "signed_flow", "q": qs, "ages": ages, "b": bs, "horizons": horizons,
        "b_ce": b_ce.tolist(), "b_survival": b_sv.tolist(), "b_ce_test_optimal": b_ce_test.tolist(),
        "risky_share_ce": (1 - b_ce).tolist(), "ce_test_at_optimum": S.to_list(full_ce, 2),
        "survival_test_at_ce_opt": [[float(SV_te[a, q, bs.index(b_ce[a, q])]) for q in range(nQ)] for a in range(nA)],
        "policies": {"age_only": b_age, "q_only": b_q, "target_date_bond_share": td,
                     "oos_delta_vs_full": {"age_only": S.to_list(d_age), "q_only": S.to_list(d_q),
                                           "target_date": S.to_list(d_td)},
                     "oos_mean_delta": {"age_only": float(np.mean(d_age)), "q_only": float(np.mean(d_q)),
                                        "target_date": float(np.mean(d_td))},
                     "oos_delta_ci": {n: [float(np.mean(m) - 1.96 * np.std(m) / np.sqrt(m.size)),
                                          float(np.mean(m) + 1.96 * np.std(m) / np.sqrt(m.size))]
                                      for n, m in (("age_only", d_age), ("q_only", d_q), ("target_date", d_td))},
                     "note": "restricted policies are fitted on training paths and scored on disjoint test paths "
                             "relative to the cell-optimal (full) policy; negative = welfare loss"},
        "slopes": slopes, "funded_ratio": S.to_list(funded_ratio, 4),
        "funded_ratio_basis": {"real_rate": rr, "source": rr_src, "mortality": "SSA period table, unisex",
                               "definition": "W_ref / PV(planned real net draws); net contributors have no "
                                             "portfolio liability (shown as not applicable)"},
        "persona": persona, "universe": S.universe_block(u), "n_paths": spec.scenario.n_paths,
        "definitions": {"q": "planned annual net draw / W_ref (negative = contribution), exogenous",
                        "ce": "CRRA(gamma=%g) CE of terminal real wealth + funded draws" % gamma,
                        "survival": "P(no unmet planned draw within min(%d, 95-age) years)" % spec.horizon_years,
                        "age_channel": "horizon length and survival only (no labour income in the q-surface)"},
        "warnings": S.common_warnings(u, S.get_tensor(S.experiment_spec(spec.data, spec.scenario, S.StudyInvestor(
            age=ages[0], horizon_years=horizons[0]), spec.preferences))),
        "timings": {}, "summary": {"universe": u.name, "n_cells": nA * nQ,
                                   "mean_oos_loss_age_only": float(np.mean(d_age))},
    }


def _persona_sched(age0, T, assets, eq, bd, b_fn):
    ages = age0 + np.arange(T) / 12.0
    sched = np.zeros((T, 1, len(assets)))
    for t in range(T):
        b = float(np.clip(b_fn(ages[t]), 0, 1))
        sched[t, 0, assets.index(eq)] = 1 - b
        sched[t, 0, assets.index(bd)] += 0.8 * b
        cash = assets.index("tbill") if "tbill" in assets else assets.index(bd)
        sched[t, 0, cash] += 0.2 * b
    return sched


def _persona(spec: SignedFlowSpec, u, b_ce, ages, qs, bs, tr) -> dict[str, Any]:
    """Synthetic, labelled persona (not an inferred real household)."""
    age0, ret = 30.0, 65.0
    inv = S.StudyInvestor(age=age0, retirement_age=ret, horizon_years=int(95 - age0), initial_wealth=50_000.0,
                          income=spec.persona_income, pension=20_000.0, savings_rate=0.12, mortality=True)
    pr = spec.preferences
    es = S.experiment_spec(spec.data, spec.scenario.model_copy(update={"n_paths": 1000}), inv, pr)
    ten = S.get_tensor(es)
    ctx = S.get_context(es, ten, es.scenario.seed)
    T = ten.n_months
    assets = ten.assets
    # planned signed-flow profile: contributions before 65 (q<0 relative to planned wealth), 4% draw after
    plan_q = lambda a: -0.05 if a < ret - 10 else (-0.02 if a < ret else 0.04)  # noqa: E731
    qa = np.array(qs)
    aa = np.array(ages, dtype=float)

    def q_aware(a):
        ai = int(np.argmin(np.abs(aa - a)))
        qi = int(np.argmin(np.abs(qa - plan_q(a))))
        return b_ce[ai, qi]

    glide = lambda a: 1 - float(target_date_equity(np.array([a]))[0])  # noqa: E731
    out = {}
    for name, fn in (("target_date", glide), ("q_aware_plan", q_aware)):
        sched = _persona_sched(age0, T, assets, spec.equity, spec.bond, fn)
        o = S.run(ctx, sched, tr, rate=0.04, record=True, trace=0, util_floor=pr.util_floor_annual)
        Y = o.cons_y.shape[1]
        retire_y = int(ret - age0)
        net_flow = (o.desired_y - o.cons_y)  # placeholder overwritten below
        contrib = np.zeros(Y)
        trace = o.trace
        for t in range(T):
            contrib[t // 12] += trace["flow"][t, 2] - trace["flow"][t, 1]
        succ = S.success(o.first_shortfall, T)
        out[name] = {
            "wealth_fan": S.fan(o.wealth_y), "consumption_fan": S.fan(o.cons_y), "retire_year_index": retire_y,
            "weights_by_year": S.to_list(o.weights_y.mean(axis=0), 4), "p_success_to_95": float(succ.mean()),
            "ce": S.ce_of(o, pr.gamma), "rebalances_per_year": float(o.n_trades.mean() / max(Y, 1)),
            "net_flow_example_path": S.to_list(contrib, 2),
            "wealth_at_retirement": S.fan(o.wealth_y[:, retire_y:retire_y + 1])}
        del net_flow
    # accumulation contribution frontier (LC-06): P(W_65 >= multiple x final income) by savings x start age
    front = {"savings": list(spec.persona_savings), "start_ages": list(spec.persona_start_ages), "policies": {}}
    for name, fn in (("target_date", glide), ("q_aware_plan", q_aware)):
        grid = []
        for sa in spec.persona_start_ages:
            row = []
            for s in spec.persona_savings:
                inv2 = S.StudyInvestor(age=sa, retirement_age=ret, horizon_years=int(ret - sa), initial_wealth=10_000.0,
                                       income=spec.persona_income, pension=0.0, savings_rate=s, mortality=False)
                es2 = S.experiment_spec(spec.data, spec.scenario.model_copy(update={"n_paths": 800}), inv2, pr)
                ten2 = S.get_tensor(es2)
                ctx2 = S.get_context(es2, ten2, es2.scenario.seed)
                Tw = int(round((ret - sa) * 12))
                sched = _persona_sched(sa, Tw, ten2.assets, spec.equity, spec.bond, fn)
                o = S.run(ctx2, sched, tr, rate=0.0, tensor=ten2.head(Tw))
                final_inc = ctx2.labor[:, Tw - 12:Tw].sum(axis=1)
                row.append(float(np.mean(o.terminal >= spec.persona_target_multiple * final_inc)))
            grid.append(row)
        front["policies"][name] = grid
    front["definition"] = ("P(real wealth at 65 >= %.0fx final-year labour income), CGM college income profile, "
                           "$10k starting wealth" % spec.persona_target_multiple)
    years_rel = (np.arange(int(95 - age0)) + age0 - ret).tolist()
    return {"label": "Synthetic persona A (illustrative household, not a real client)", "start_age": age0,
            "retirement_age": ret, "income": spec.persona_income, "savings_rate": 0.12, "pension": 20_000.0,
            "withdrawal_rate": 0.04, "assets": list(assets), "years_relative": years_rel,
            "planned_q": [plan_q(age0 + y) for y in range(int(95 - age0))], "policies": out,
            "contribution_frontier": front,
            "equations": ["I_t = W_t + Y_t^save - D_t^funded", "D_t^funded = min(D_t^desired, W_t)",
                          "W_{t+1} = sum_i h_{i,t}^{post-trade} (1 + R_{i,t+1})", "U_t^unmet = D_t^desired - D_t^funded"]}


def trace_persona(spec: SignedFlowSpec, policy: str, path: int) -> dict[str, Any]:
    from lifecycle.studies.frontier import trace_payload

    age0, ret = 30.0, 65.0
    inv = S.StudyInvestor(age=age0, retirement_age=ret, horizon_years=int(95 - age0), initial_wealth=50_000.0,
                          income=spec.persona_income, pension=20_000.0, savings_rate=0.12, mortality=True)
    es = S.experiment_spec(spec.data, spec.scenario.model_copy(update={"n_paths": 1000}), inv, spec.preferences)
    ten = S.get_tensor(es)
    ctx = S.get_context(es, ten, es.scenario.seed)
    glide = lambda a: 1 - float(target_date_equity(np.array([a]))[0])  # noqa: E731
    sched = _persona_sched(age0, ten.n_months, ten.assets, spec.equity, spec.bond, glide)
    o = S.run(ctx, sched, S.strategy(spec.rebalancer, spec.costs), rate=0.04, record=True, trace=path)
    return trace_payload(o, ctx, ten.assets, path)


__all__ = ["SignedFlowSpec", "run_signed_flow", "trace_persona", "ledger"]
