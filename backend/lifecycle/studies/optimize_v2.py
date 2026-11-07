"""Page I: multi-objective allocation and policy surfaces (CE vs survival vs shortfall, robustness)."""
from itertools import combinations
from math import factorial
from typing import Any

import numpy as np
from pydantic import Field
from scipy.optimize import minimize

from lifecycle.engine import fixed_income
from lifecycle.engine.optimize.static import simplex_grid
from lifecycle.studies import common as S


class OptimizeSpec(S.Frozen):
    data: S.StudyData = Field(default_factory=lambda: S.StudyData(universe="core_duration"))
    scenario: S.StudyScenario = Field(default_factory=lambda: S.StudyScenario(n_paths=2000))
    investor: S.StudyInvestor = Field(default_factory=lambda: S.StudyInvestor(horizon_years=30))
    preferences: S.StudyPrefs = Field(default_factory=S.StudyPrefs)
    costs: S.StudyCosts = Field(default_factory=S.StudyCosts)
    withdrawal: float = 0.045
    target: float = 0.90
    sleeves: tuple[str, ...] = ("us_eq", "ust_10y", "tbill", "ust_30y", "ust_2y")
    simplex_divisions: int = Field(10, ge=2, le=20)
    r_grid: tuple[float, ...] = (0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08)
    funded_ratios: tuple[float, ...] = (0.6, 0.8, 1.0, 1.2, 1.5, 2.0)
    horizons_years: tuple[int, ...] = (10, 20, 30, 40)
    spending: float = 40_000.0
    generators: tuple[str, ...] = ("bootstrap", "student_t", "markov_switching")
    n_param_boot: int = Field(8, ge=0, le=100)
    label: str | None = None


def _eq_bond(assets, e, bond="ust_10y"):
    return S.weights_vector({"us_eq": e, bond: 1 - e} if e < 1 else {"us_eq": 1.0}, assets)


def run_optimize(spec: OptimizeSpec, progress: S.Progress) -> dict[str, Any]:
    u = S.universe_or_raise(spec.data)
    es, ctx, train = S.train_test(spec.data, spec.scenario, spec.investor, spec.preferences)
    ten = ctx.tensor
    assets = ten.assets
    sleeves = [a for a in spec.sleeves if a in assets]
    gamma = spec.preferences.gamma
    mh = spec.investor.horizon_years * 12
    tr = S.strategy("calendar_12m", spec.costs)
    cov = S.hist_cov(u, assets)
    r0 = spec.withdrawal

    def evw(c, w, rate=r0, g=None, tensor=None):
        return S.run(c, w, tr, rate=rate, gamma=g, util_floor=spec.preferences.util_floor_annual, tensor=tensor)

    # OP-01 Pareto frontier over the static simplex of sleeves (train for selection, test for reporting)
    progress("pareto", 0.05)
    pts = simplex_grid(len(sleeves), spec.simplex_divisions if len(sleeves) <= 3 else max(4, spec.simplex_divisions // 2))
    cloud = []
    for p in pts:
        w = S.weights_vector({s: v for s, v in zip(sleeves, p)}, assets) if p.sum() > 0 else None
        if w is None:
            continue
        o = evw(ctx, w)
        sb = S.success(o.first_shortfall, mh)
        cloud.append({"weights": dict(zip(sleeves, np.round(p, 4).tolist())), "ce": S.ce_of(o, gamma),
                      "p_fail": float(1 - sb.mean()), "cvar95_unmet": S.cvar(o.unmet, 0.95),
                      "feasible": bool(sb.mean() >= spec.target)})
    ce_arr = np.array([c["ce"] for c in cloud])
    pf = np.array([c["p_fail"] for c in cloud])
    for i, c in enumerate(cloud):
        c["pareto"] = bool(not np.any((ce_arr >= c["ce"]) & (pf <= c["p_fail"]) & ((ce_arr > c["ce"]) | (pf < c["p_fail"]))))

    # OP-02 optimal equity share by withdrawal x starting regime (bootstrap start pools)
    progress("regime surface", 0.25)
    eqs = np.linspace(0, 1, 11)
    reg_surface = {"r": list(spec.r_grid), "regimes": [], "equity": [], "bond_marginal": []}
    starts: list[int | None] = [None] + (list(range(ten.n_regimes)) if ten.n_regimes > 1 else [])
    for sr in starts:
        if sr is None:
            c2 = ctx
            lab = "all starts"
        else:
            t2 = S.get_tensor(es, n_paths=min(spec.scenario.n_paths, 1000), start_regime=sr, seed=spec.scenario.seed + 31)
            c2 = S.get_context(es, t2, spec.scenario.seed + 31)
            lab = "start regime %d" % sr
        row, bm = [], []
        for r in spec.r_grid:
            ces = [S.ce_of(evw(c2, _eq_bond(assets, e), rate=r), gamma) for e in eqs]
            row.append(float(eqs[int(np.argmax(ces))]))
            a = evw(c2, _eq_bond(assets, 0.6), rate=r)
            b = evw(c2, _eq_bond(assets, 1.0), rate=r)
            d = S.delta_block(a, b, gamma, n_boot=100)
            bm.append({"delta": d["delta"], "lo": d["lo"], "hi": d["hi"]})
        reg_surface["regimes"].append(lab)
        reg_surface["equity"].append(row)
        reg_surface["bond_marginal"].append(bm)
    reg_surface["note"] = "bond_marginal = paired dCE of 60/40 vs 100% equity (value of a 40% bond sleeve)"

    # OP-03 Shapley contributions of sleeves at the CE-optimal static mix with path-bootstrap CI
    progress("shapley", 0.4)
    best = max(cloud, key=lambda c: c["ce"])
    players = [s for s in sleeves if s != "us_eq"]
    vals: dict[frozenset, Any] = {}

    def value(coal):
        if coal in vals:
            return vals[coal]
        w = {"us_eq": 0.4}
        for s in coal:
            w[s] = 0.6 / len(coal)
        if not coal:
            w = {"us_eq": 1.0}
        vals[coal] = evw(ctx, S.weights_vector(w, assets)).utility
        return vals[coal]

    n = len(players)
    rng = np.random.default_rng(5)
    boots = [rng.integers(0, ten.n_paths, ten.n_paths) for _ in range(60)]
    from lifecycle.engine.lifecycle.utility import ce_from_utility

    def ce_u(uarr):
        return ce_from_utility(float(uarr.mean()), gamma, ctx.disc[:ten.n_months].sum()) * S.SCALE

    shap = []
    for p in players:
        others = [q for q in players if q != p]
        terms = []
        for k in range(n):
            for comb in combinations(others, k):
                s = frozenset(comb)
                wgt = factorial(k) * factorial(n - k - 1) / factorial(n)
                terms.append((wgt, value(s | {p}), value(s)))
        point = sum(wg * (ce_u(a) - ce_u(b)) for wg, a, b in terms)
        bs = [sum(wg * (ce_u(a[ix]) - ce_u(b[ix])) for wg, a, b in terms) for ix in boots]
        shap.append({"sleeve": p, "shapley_ce": point, "lo": float(np.quantile(bs, 0.025)), "hi": float(np.quantile(bs, 0.975))})
    marginal = []
    for p in players:
        base_w = {"us_eq": 0.6, "ust_10y": 0.4} if "ust_10y" in assets else {"us_eq": 1.0}
        a = evw(ctx, S.weights_vector(base_w, assets))
        w2 = dict(base_w)
        w2[p] = w2.get(p, 0) + 0.1
        b = evw(ctx, S.weights_vector(w2, assets))
        marginal.append({"sleeve": p, **S.delta_block(b, a, gamma, n_boot=100)})

    # OP-04 policy uncertainty band: CE-optimal equity share across path bootstraps, generators, parameter refits
    progress("uncertainty", 0.55)
    outs = [evw(ctx, _eq_bond(assets, e)) for e in eqs]
    U = np.array([o.utility for o in outs])
    sd = outs[0].sum_disc
    b_path = []
    for ix in boots:
        mu = U[:, ix].mean(axis=1)
        b_path.append(float(eqs[int(np.argmax([ce_from_utility(m, gamma, sd) for m in mu]))]))
    b_gen = {}
    for g in spec.generators:
        try:
            esg = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences, generator=g, n_paths=1000)
            tg = S.get_tensor(esg)
            cg = S.get_context(esg, tg, esg.scenario.seed)
            b_gen[g] = float(eqs[int(np.argmax([S.ce_of(evw(cg, _eq_bond(assets, e)), gamma) for e in eqs]))])
        except Exception as exc:
            b_gen[g] = "error: " + str(exc)[:100]
    b_param = []
    for k in range(spec.n_param_boot):
        # outer parameter bootstrap: block-resample the calibration history, refit the bootstrap generator
        from lifecycle.engine.scenarios.base import generate
        from lifecycle.engine.scenarios.bootstrap import StationaryBootstrap

        r_ = np.random.default_rng(1000 + k)
        H = u.real_array()
        infl_h = u.inflation.to_numpy()
        L = len(H)
        idx = []
        while len(idx) < L:
            s0 = int(r_.integers(0, L))
            idx.extend(((s0 + np.arange(24)) % L).tolist())
        idx = np.array(idx[:L])
        m = StationaryBootstrap(H[idx], infl_h[idx])
        tk = generate(m, assets, 600, ten.n_months, 77 + k)
        from lifecycle.studies.common import run as _run

        ctxk = S.get_context(S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences, n_paths=600),
                             tk, 77 + k)
        b_param.append(float(eqs[int(np.argmax([S.ce_of(_run(ctxk, _eq_bond(assets, e), tr, rate=r0), gamma)
                                                 for e in eqs]))]))
    band = {"path_bootstrap": {"q05": float(np.quantile(b_path, 0.05)), "q50": float(np.median(b_path)),
                               "q95": float(np.quantile(b_path, 0.95)), "values": b_path},
            "generators": b_gen, "parameter_refits": b_param,
            "note": "the CE-optimal equity share is reported as a range; a single point is not supported"}

    # OP-05 funding-ratio policy surface: wealth = FR x PV(spending) on the real curve
    progress("funding ratio", 0.68)
    try:
        from lifecycle.fixed_income_v2 import _curve

        _, rm, rz = _curve("real", None)
    except Exception:
        rm, rz = np.array([2.0, 20.0]), np.array([0.015, 0.015])
    fr_surface = {"funded_ratios": list(spec.funded_ratios), "horizons": [], "equity": [], "success": [],
                  "constraints": "long-only equity/10Y; equity grid 0..1 step 0.1"}
    for h in spec.horizons_years:
        if h > spec.investor.horizon_years:
            continue
        times = np.arange(1, h + 1, dtype=float)
        pv = fixed_income.liability_pv_duration(np.full(h, spec.spending), times, rm, rz)["pv"]
        row_e, row_s = [], []
        for fr in spec.funded_ratios:
            W0 = fr * pv
            rate = spec.spending / W0
            best_e, best_ce, best_s = 0.0, -np.inf, 0.0
            for e in eqs:
                o = evw(ctx, _eq_bond(assets, e), rate=rate, tensor=ten.head(h * 12))
                ce = S.ce_of(o, gamma)
                if ce > best_ce:
                    best_e, best_ce, best_s = float(e), ce, float(S.success(o.first_shortfall, h * 12).mean())
            row_e.append(best_e)
            row_s.append(best_s)
        fr_surface["horizons"].append(h)
        fr_surface["equity"].append(row_e)
        fr_surface["success"].append(row_s)

    # OP-06 static vs fitted glidepath vs parametric (train/test) and DP pointer
    progress("policy classes", 0.78)
    classes = []
    for name, fn in (("static best constant", lambda e: _eq_bond(assets, e)),):
        tr_ce = [S.ce_of(evw(train, fn(e)), gamma) for e in eqs]
        ebest = eqs[int(np.argmax(tr_ce))]
        te_ce = [S.ce_of(evw(ctx, fn(e)), gamma) for e in eqs]
        classes.append({"policy": name, "selected": float(ebest), "ce_train": float(max(tr_ce)),
                        "ce_test": float(te_ce[int(np.argmax(tr_ce))]), "ce_test_oracle": float(max(te_ce)),
                        "holdout_regret": float(1 - te_ce[int(np.argmax(tr_ce))] / max(te_ce))})
    # linear glidepath in years since retirement fitted on train
    T = ten.n_months
    best_g = None
    for a0 in (0.4, 0.6, 0.8):
        for a1 in (-0.2, -0.1, 0.0, 0.1):
            share = np.clip(a0 + a1 * np.arange(T) / 120.0, 0, 1)
            sched = np.zeros((T, 1, len(assets)))
            sched[:, 0, assets.index("us_eq")] = share
            sched[:, 0, assets.index("ust_10y")] = 1 - share
            ce_tr = S.ce_of(evw(train, sched), gamma)
            if best_g is None or ce_tr > best_g[0]:
                best_g = (ce_tr, a0, a1, sched)
    ce_te = S.ce_of(evw(ctx, best_g[3]), gamma)
    classes.append({"policy": "fitted glidepath (equity = a0 + a1 * decades since retirement)",
                    "selected": [best_g[1], best_g[2]], "ce_train": best_g[0], "ce_test": ce_te,
                    "holdout_regret": None})
    if ten.n_regimes > 1:
        best_r = None
        for e0 in eqs[::2]:
            for e1 in eqs[::2]:
                per = np.array([_eq_bond(assets, e0), _eq_bond(assets, e1)] + [_eq_bond(assets, e1)] * (ten.n_regimes - 2))
                sched = np.broadcast_to(per, (T, ten.n_regimes, len(assets))).copy()
                c = S.ce_of(evw(train, sched), gamma)
                if best_r is None or c > best_r[0]:
                    best_r = (c, e0, e1, sched)
        classes.append({"policy": "regime-conditional (filtered, lagged signal)", "selected": [best_r[1], best_r[2]],
                        "ce_train": best_r[0], "ce_test": S.ce_of(evw(ctx, best_r[3]), gamma), "holdout_regret": None})
        orc = ten.decision
        ten.decision = ten.regime.copy()
        classes.append({"policy": "ORACLE regime (contemporaneous latent state; not tradable)",
                        "selected": [best_r[1], best_r[2]], "ce_test": S.ce_of(evw(ctx, best_r[3]), gamma),
                        "oracle": True})
        ten.decision = orc
    classes.append({"policy": "grid DP (reduced 3-asset problem)", "pointer": "see Policy Optimizer DP runs (legacy "
                    "engine, kind=experiment, policy.type=dp); not re-run here", "oracle": False})

    # OP-07 objective switch
    progress("objectives", 0.86)
    res_e = []
    for e, o in zip(eqs, outs):
        res_e.append({"equity": float(e), "ce": S.ce_of(o, gamma), "success": float(S.success(o.first_shortfall, mh).mean()),
                      "cvar95_unmet": S.cvar(o.unmet, 0.95)})
    gen_ce = {}
    for g in spec.generators:
        try:
            esg = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences, generator=g, n_paths=800)
            tg = S.get_tensor(esg)
            cg = S.get_context(esg, tg, esg.scenario.seed)
            gen_ce[g] = [S.ce_of(evw(cg, _eq_bond(assets, e)), gamma) for e in eqs]
        except Exception:
            continue
    M = np.array(list(gen_ce.values())) if gen_ce else np.zeros((1, len(eqs)))
    regret = ((M.max(axis=1, keepdims=True) - M) / np.maximum(M.max(axis=1, keepdims=True), 1e-9)).max(axis=0)
    feasible = [r for r in res_e if r["success"] >= spec.target]
    objectives = [
        {"objective": "maximise CE", "equity": max(res_e, key=lambda r: r["ce"])["equity"]},
        {"objective": "maximise %dy success" % spec.investor.horizon_years,
         "equity": max(res_e, key=lambda r: (r["success"], -r["equity"]))["equity"]},
        {"objective": "minimise shortfall CVaR95", "equity": min(res_e, key=lambda r: r["cvar95_unmet"])["equity"]},
        {"objective": "robust minimax regret (generators)", "equity": float(eqs[int(np.argmin(regret))]),
         "max_regret": float(regret.min())},
        {"objective": "max CE s.t. success >= %.0f%%" % (spec.target * 100),
         "equity": max(feasible, key=lambda r: r["ce"])["equity"] if feasible else None,
         "constraint": "infeasible: no equity share meets the target" if not feasible else "binding" if
         max(feasible, key=lambda r: r["ce"])["equity"] != max(res_e, key=lambda r: r["ce"])["equity"] else "slack"}]
    for ob in objectives:
        if ob["equity"] is not None:
            rr = res_e[int(round(ob["equity"] * 10))]
            ob.update({"ce": rr["ce"], "success": rr["success"], "cvar95_unmet": rr["cvar95_unmet"]})

    # OP-08 risk budget & duration for the CE-optimal simplex point
    try:
        from lifecycle.fixed_income_v2 import _curve

        _, cm, cz = _curve("nominal", None)
    except Exception:
        cm = cz = None
    wbest = S.weights_vector(best["weights"], assets)
    rc = wbest * (cov @ wbest)
    tot = float(wbest @ cov @ wbest)
    durs = []
    for a in assets:
        if a.startswith("ust_") and cm is not None:
            mt = float(a.split("_")[1][:-1])
            y = float(np.interp(mt, cm, cz))
            durs.append(fixed_income.modified_duration(y, y, mt))
        else:
            durs.append(1 / 12 if a == "tbill" else 0.0)
    budget = {"weights": dict(zip(assets, wbest.tolist())), "risk_contribution": dict(zip(assets, (rc / tot).tolist())),
              "vol_annual": float(np.sqrt(tot * 12)), "duration_by_sleeve": dict(zip(assets, durs)),
              "portfolio_duration": float(np.dot(wbest, durs)),
              "liquidity_months_of_spending": float(wbest[assets.index("tbill")] * 12 / r0) if "tbill" in assets else None,
              "bounds": {"min": 0.0, "max": 1.0}}

    # OP-09 parameter stability tornado (CE-optimal equity share)
    progress("tornado", 0.92)
    base_e = max(res_e, key=lambda r: r["ce"])["equity"]

    def opt_e(c, g=None, rate=r0):
        return float(eqs[int(np.argmax([S.ce_of(evw(c, _eq_bond(assets, e), rate=rate, g=g), g or gamma) for e in eqs]))])

    tornado = [{"parameter": "gamma 2 / 8", "low": opt_e(ctx, 2.0), "high": opt_e(ctx, 8.0)},
               {"parameter": "withdrawal -1pp / +1pp", "low": opt_e(ctx, rate=r0 - 0.01), "high": opt_e(ctx, rate=r0 + 0.01)}]
    for lab, d2 in (("sample window first/second half", None),):
        mid = u.real.index[len(u.real) // 2].date().isoformat()
        vals2 = []
        for dd in (spec.data.model_copy(update={"calibration_end": mid}),
                   spec.data.model_copy(update={"calibration_start": mid})):
            esw = S.experiment_spec(dd, spec.scenario, spec.investor, spec.preferences, n_paths=800)
            tw = S.get_tensor(esw)
            vals2.append(opt_e(S.get_context(esw, tw, esw.scenario.seed)))
        tornado.append({"parameter": lab, "low": vals2[0], "high": vals2[1]})
    esb = [S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences.model_copy(update={"beta_annual": b}),
                             n_paths=800) for b in (0.95, 0.99)]
    tornado.append({"parameter": "beta 0.95 / 0.99",
                    "low": opt_e(S.get_context(esb[0], S.get_tensor(esb[0]), 1)),
                    "high": opt_e(S.get_context(esb[1], S.get_tensor(esb[1]), 1))})

    # OP-10 optimisation trace: SLSQP on the static sleeve weights (training paths)
    trace = []

    def obj(z):
        w = np.abs(z) / max(np.abs(z).sum(), 1e-9)
        ce = S.ce_of(evw(train, S.weights_vector(dict(zip(sleeves, w)), assets)), gamma)
        trace.append({"iteration": len(trace), "ce": ce, "constraint_residual": float(abs(np.abs(z).sum() - 1))})
        return -ce / 1e4

    z0 = np.full(len(sleeves), 1 / len(sleeves))
    resopt = minimize(obj, z0, method="SLSQP", bounds=[(0, 1)] * len(sleeves),
                      constraints=[{"type": "eq", "fun": lambda z: np.sum(z) - 1}], options={"maxiter": 30, "ftol": 1e-6})
    opt_trace = {"evaluations": trace, "converged": bool(resopt.success), "message": str(resopt.message),
                 "solution": dict(zip(sleeves, np.round(np.abs(resopt.x) / np.abs(resopt.x).sum(), 4).tolist())),
                 "note": "objective evaluations include finite-difference gradient calls; non-convergence is reported"}
    return {"kind": "optimize", "universe": S.universe_block(u), "scenario": S.scenario_block(ten),
            "n_paths": ten.n_paths, "withdrawal": r0, "target": spec.target, "sleeves": sleeves, "pareto": cloud,
            "regime_surface": reg_surface, "shapley": shap, "marginal": marginal, "uncertainty_band": band,
            "funding_ratio_surface": fr_surface, "policy_classes": classes, "objectives": objectives,
            "by_equity": res_e, "risk_budget": budget, "tornado": tornado, "base_equity": base_e,
            "optimisation_trace": opt_trace, "warnings": S.common_warnings(u, ten), "timings": {},
            "summary": {"universe": u.name, "best_equity": base_e}}
