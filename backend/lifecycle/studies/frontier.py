"""E01-E03 / F1: withdrawal-rate x bond-share survival surface and the bond-necessity frontier (brief 2.4).

b_min(r, T; s*) = inf{ b : P_success(b, r, T) >= s* } is solved on the *feasible set* of the grid, which may
be empty, start at b = 0, or be disconnected. The whole surface is bootstrapped jointly (path resampling)
and b_min is re-solved in every replicate, so the reported interval carries the selection step and the
share of replicates where b_min is not identified.
"""
from typing import Any

import numpy as np
from pydantic import Field

from lifecycle.data import panel
from lifecycle.engine.lifecycle import ledger
from lifecycle.studies import common as S


class FrontierSpec(S.Frozen):
    data: S.StudyData = Field(default_factory=lambda: S.StudyData(universe="core_long_history"))
    scenario: S.StudyScenario = Field(default_factory=S.StudyScenario)
    investor: S.StudyInvestor = Field(default_factory=lambda: S.StudyInvestor(horizon_years=40))
    preferences: S.StudyPrefs = Field(default_factory=S.StudyPrefs)
    costs: S.StudyCosts = Field(default_factory=S.StudyCosts)
    equity: str = "us_eq"
    bond: str = "ust_10y"
    rebalancer: str = "calendar_12m"
    r_start: float = Field(0.0, ge=0, le=0.2)
    r_stop: float = Field(0.10, ge=0, le=0.2)
    r_step: float = Field(0.0025, gt=0, le=0.05)
    b_step: float = Field(0.05, gt=0, le=0.5)
    targets: tuple[float, ...] = (0.80, 0.85, 0.90, 0.95)
    horizons_years: tuple[int, ...] = (10, 20, 30, 40)
    main_horizon: int = 30
    main_target: float = 0.90
    n_boot: int = Field(200, ge=0, le=1000)
    alt_generators: tuple[str, ...] = ("student_t", "markov_switching")
    alt_n_paths: int = Field(1000, ge=100, le=10000)
    alt_windows: tuple[tuple[str, str], ...] = (("1953-01-01", "1989-12-31"), ("1990-01-01", "2026-12-31"))
    gammas: tuple[float, ...] = (2.0, 4.0, 6.0, 8.0)
    bond_assets: tuple[str, ...] = ("tbill", "ust_5y", "ust_10y")
    label: str | None = None


def _grid(a: float, b: float, step: float) -> list[float]:
    n = int(round((b - a) / step))
    return [round(a + i * step, 6) for i in range(n + 1)]


def solve_bmin(p: np.ndarray, bs: list[float], target: float) -> dict[str, Any]:
    """p: success over bond shares for one r. Returns b_min, the identified bracket and feasible intervals."""
    feas = p >= target
    out: dict[str, Any] = {"feasible_any": bool(feas.any())}
    if not feas.any():
        out.update({"b_min": None, "bracket": None, "intervals": [], "status": "no_feasible_allocation"})
        return out
    i = int(np.argmax(feas))
    intervals = []
    start = None
    for k in range(len(bs)):
        if feas[k] and start is None:
            start = bs[k]
        if (not feas[k] or k == len(bs) - 1) and start is not None:
            end = bs[k] if feas[k] else bs[k - 1]
            intervals.append([start, end])
            start = None
    out.update({"b_min": bs[i], "bracket": [bs[i - 1] if i > 0 else None, bs[i]], "intervals": intervals,
                "status": "no_bonds_needed" if i == 0 else ("disconnected" if len(intervals) > 1 else "identified")})
    return out


def _surface(ctx, assets, eq, bd, rs, bs, tr, horizons, keep_first: bool, util_floor: float,
             cov=None, gamma=None, progress=None, lo=0.0, hi=1.0):
    nb, nr = len(bs), len(rs)
    P = np.zeros((len(horizons), nb, nr))
    CE = np.zeros((nb, nr))
    CE_SE = np.zeros((nb, nr))
    UNMET = np.zeros((nb, nr))
    CVAR = np.zeros((nb, nr))
    UD = np.zeros((nb, nr))
    firsts = {} if keep_first else None
    utils = {} if keep_first else None
    g = ctx.prefs.gamma if gamma is None else gamma
    k = 0
    for bi, b in enumerate(bs):
        w = np.zeros(len(assets))
        w[assets.index(eq)] += 1 - b
        w[assets.index(bd)] += b
        for ri, r in enumerate(rs):
            out = S.run(ctx, w, tr, rate=r, util_floor=util_floor, gamma=g, cov=cov)
            for hi_, h in enumerate(horizons):
                P[hi_, bi, ri] = S.success(out.first_shortfall, h * 12).mean()
            ceb = S.ce_block(out, g)
            CE[bi, ri], CE_SE[bi, ri] = ceb["ce"], ceb["se"]
            UNMET[bi, ri] = out.unmet.mean()
            CVAR[bi, ri] = S.cvar(out.unmet, 0.95)
            UD[bi, ri] = S.until_death_success(out.first_shortfall, ctx.survival)
            if keep_first:
                firsts[(bi, ri)] = out.first_shortfall.astype(np.int32)
                utils[(bi, ri)] = out.utility
            k += 1
            if progress is not None and k % 25 == 0:
                progress("simulating", lo + (hi - lo) * k / (nb * nr))
    return P, CE, CE_SE, UNMET, CVAR, UD, firsts, utils


def run_frontier(spec: FrontierSpec, progress: S.Progress) -> dict[str, Any]:
    u = S.universe_or_raise(spec.data)
    if spec.bond not in u.assets or spec.equity not in u.assets:
        raise S.IncompatibleUniverse("bond '%s' / equity '%s' not in universe %s" % (spec.bond, spec.equity, u.name))
    horizons = tuple(h for h in spec.horizons_years if h <= spec.investor.horizon_years)
    if spec.main_horizon not in horizons:
        raise ValueError("main_horizon must be one of horizons_years and <= investor horizon")
    progress("generating_scenarios", 0.02)
    es = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences)
    ten = S.get_tensor(es)
    ctx = S.get_context(es, ten, es.scenario.seed)
    assets = ten.assets
    rs = _grid(spec.r_start, spec.r_stop, spec.r_step)
    bs = _grid(0.0, 1.0, spec.b_step)
    tr = S.strategy(spec.rebalancer, spec.costs)
    uf = spec.preferences.util_floor_annual
    P, CE, CE_SE, UNMET, CVAR, UD, firsts, utils = _surface(ctx, assets, spec.equity, spec.bond, rs, bs, tr,
                                                            horizons, True, uf, progress=progress, lo=0.05, hi=0.55)
    N = ten.n_paths
    iid = ten.meta.get("generator") != "historical"
    hidx = {h: i for i, h in enumerate(horizons)}
    mh = hidx[spec.main_horizon]

    # Wilson CIs per cell for the main horizon
    lo = np.zeros_like(P)
    hi = np.zeros_like(P)
    for a in range(P.shape[0]):
        for b in range(P.shape[1]):
            for c in range(P.shape[2]):
                lo[a, b, c], hi[a, b, c] = S.wilson(float(P[a, b, c]), N) if iid else (np.nan, np.nan)

    # point thresholds
    thresholds: dict[str, Any] = {}
    for h in horizons:
        for s in spec.targets:
            key = "%d|%.2f" % (h, s)
            thresholds[key] = [dict(r=rs[ri], **solve_bmin(P[hidx[h], :, ri], bs, s)) for ri in range(len(rs))]

    # joint bootstrap of the whole surface -> b_min distribution
    progress("uncertainty", 0.6)
    boot: dict[str, Any] = {}
    if spec.n_boot > 0:
        rng = np.random.default_rng(spec.scenario.seed + 11)
        counts = np.stack([np.bincount(rng.integers(0, N, N), minlength=N) for _ in range(spec.n_boot)], axis=1)
        for h in horizons:
            ind = np.zeros((len(bs) * len(rs), N), dtype=np.float32)
            for (bi, ri), f in firsts.items():
                ind[bi * len(rs) + ri] = (f < 0) | (f >= h * 12)
            Pb = (ind @ counts / N).reshape(len(bs), len(rs), spec.n_boot)
            for s in spec.targets:
                key = "%d|%.2f" % (h, s)
                rows = []
                for ri in range(len(rs)):
                    feas = Pb[:, ri, :] >= s
                    anyf = feas.any(axis=0)
                    first = np.where(anyf, np.argmax(feas, axis=0), -1)
                    vals = np.array([bs[i] for i in first if i >= 0])
                    rows.append({"r": rs[ri], "share_unidentified": float(1 - anyf.mean()),
                                 "share_zero_bonds": float(np.mean(first == 0)),
                                 "q05": float(np.quantile(vals, 0.05)) if len(vals) else None,
                                 "q50": float(np.quantile(vals, 0.5)) if len(vals) else None,
                                 "q95": float(np.quantile(vals, 0.95)) if len(vals) else None,
                                 "hist": np.histogram(vals, bins=np.arange(-0.5 * spec.b_step, 1 + spec.b_step,
                                                                           spec.b_step))[0].tolist()
                                 if len(vals) else []})
                boot[key] = rows
    # withdrawal breakpoint: first r where all-equity fails s* but a bond-containing mix passes
    breakpoints = {}
    for s in spec.targets:
        bp = None
        for ri in range(len(rs)):
            if P[mh, 0, ri] < s and (P[mh, 1:, ri] >= s).any():
                bp = rs[ri]
                break
        breakpoints["%.2f" % s] = bp
    # maximum sustainable withdrawal per bond share and target (largest grid r with p >= s*)
    max_r = {}
    for s in spec.targets:
        row = []
        for bi in range(len(bs)):
            ok = [rs[ri] for ri in range(len(rs)) if P[mh, bi, ri] >= s]
            mono = all(P[mh, bi, ri] >= P[mh, bi, ri + 1] - 1e-9 for ri in range(len(rs) - 1))
            row.append({"b": bs[bi], "max_r": max(ok) if ok else None, "monotone_in_r": bool(mono)})
        max_r["%.2f" % s] = row
    # max-r bootstrap for selected bond shares
    maxr_boot = {}
    if spec.n_boot > 0:
        ind = np.zeros((len(bs) * len(rs), N), dtype=np.float32)
        for (bi, ri), f in firsts.items():
            ind[bi * len(rs) + ri] = (f < 0) | (f >= spec.main_horizon * 12)
        Pb = (ind @ counts / N).reshape(len(bs), len(rs), spec.n_boot)
        for s in spec.targets:
            rows = []
            for bi in range(len(bs)):
                ok = Pb[bi] >= s
                vals = np.array([max([rs[ri] for ri in range(len(rs)) if ok[ri, k]], default=np.nan)
                                 for k in range(spec.n_boot)])
                v = vals[np.isfinite(vals)]
                rows.append({"b": bs[bi], "q05": float(np.quantile(v, 0.05)) if len(v) else None,
                             "q95": float(np.quantile(v, 0.95)) if len(v) else None})
            maxr_boot["%.2f" % s] = rows

    # CE-optimal vs survival-optimal bond share per r (main horizon)
    progress("summarising", 0.7)
    optima = []
    for ri, r in enumerate(rs):
        bce = int(np.argmax(CE[:, ri]))
        bsv = int(np.argmax(P[mh, :, ri] + 1e-9 * np.arange(len(bs))[::-1]))
        optima.append({"r": r, "b_ce": bs[bce], "b_survival": bs[bsv], "ce_at_ce_opt": CE[bce, ri],
                       "ce_at_surv_opt": CE[bsv, ri], "p_at_ce_opt": P[mh, bce, ri], "p_at_surv_opt": P[mh, bsv, ri],
                       "unmet_at_ce_opt": UNMET[bce, ri], "unmet_at_surv_opt": UNMET[bsv, ri],
                       "distance": abs(bs[bce] - bs[bsv])})

    # detail blocks for selected policies at headline withdrawal rates
    detail_r = [r for r in (0.03, 0.04, 0.05, 0.06) if any(abs(r - x) < 1e-9 for x in rs)]
    detail_b = [b for b in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0) if any(abs(b - x) < 1e-9 for x in bs)]
    details: dict[str, Any] = {}
    for r in detail_r:
        ri = min(range(len(rs)), key=lambda i: abs(rs[i] - r))
        for b in detail_b:
            bi = min(range(len(bs)), key=lambda i: abs(bs[i] - b))
            w = np.zeros(len(assets))
            w[assets.index(spec.equity)] += 1 - b
            w[assets.index(spec.bond)] += b
            out = S.run(ctx, w, tr, rate=r, util_floor=uf)
            details["%.4f|%.2f" % (r, b)] = {
                "first_shortfall": S.first_shortfall_block(out, ctx.investor.retire_month, spec.investor.horizon_years,
                                                           ctx.survival),
                "severity": S.severity_block(out, n_sample=250),
                "success": {str(h): S.success_block(out.first_shortfall, h * 12, iid) for h in horizons},
                "until_death": UD[bi, ri], "ce": CE[bi, ri], "ce_se": CE_SE[bi, ri]}

    # bond value across instruments at a 40% defensive share (FI-12)
    progress("summarising", 0.75)
    spectrum = []
    eq_only = np.zeros(len(assets))
    eq_only[assets.index(spec.equity)] = 1.0
    base_runs = {r: S.run(ctx, eq_only, tr, rate=r, util_floor=uf) for r in rs[::4]}
    for bond in spec.bond_assets:
        if bond not in assets:
            spectrum.append({"bond": bond, "available": False})
            continue
        row = {"bond": bond, "available": True, "r": [], "d_success": [], "d_ce": [], "d_ce_lo": [], "d_ce_hi": []}
        for r, base in base_runs.items():
            w = eq_only * 0.6
            w[assets.index(bond)] += 0.4
            out = S.run(ctx, w, tr, rate=r, util_floor=uf)
            row["r"].append(r)
            row["d_success"].append(float(S.success(out.first_shortfall, spec.main_horizon * 12).mean() -
                                          S.success(base.first_shortfall, spec.main_horizon * 12).mean()))
            d = S.delta_block(out, base, ctx.prefs.gamma, n_boot=0)
            row["d_ce"].append(d["delta"])
            row["d_ce_lo"].append(d["lo"])
            row["d_ce_hi"].append(d["hi"])
        spectrum.append(row)

    # robustness: alternative generators (coarse grid), calibration windows, gammas -> threshold forest
    progress("robustness", 0.8)
    rs_c = rs[::4] if len(rs) > 20 else rs
    bs_c = bs[::2] if len(bs) > 11 else bs
    forest: list[dict[str, Any]] = []
    mt = spec.main_target
    for h in horizons:
        for s in spec.targets:
            if h != spec.main_horizon and s != mt:
                continue
            key = "%d|%.2f" % (h, s)
            for row, brow in zip(thresholds[key], boot.get(key, [{}] * len(rs))):
                if abs(row["r"] - 0.05) < 1e-9:
                    forest.append({"dimension": "target" if h == spec.main_horizon else "horizon",
                                   "label": "s*=%.0f%%, T=%dy" % (s * 100, h), "b_min": row["b_min"],
                                   "status": row["status"], "lo": brow.get("q05"), "hi": brow.get("q95")})
    alt: dict[str, Any] = {}
    sign_stack = [(P[mh][::2 if len(bs) > 11 else 1][:, ::4 if len(rs) > 20 else 1] >= mt)]
    for g in spec.alt_generators:
        try:
            es_g = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences, generator=g,
                                     n_paths=spec.alt_n_paths)
            ten_g = S.get_tensor(es_g)
            ctx_g = S.get_context(es_g, ten_g, es_g.scenario.seed)
            Pg, CEg, *_ = _surface(ctx_g, assets, spec.equity, spec.bond, rs_c, bs_c, tr, (spec.main_horizon,),
                                   False, uf)
            th = [dict(r=r, **solve_bmin(Pg[0, :, i], bs_c, mt)) for i, r in enumerate(rs_c)]
            alt[g] = {"p_success": S.to_list(Pg[0]), "thresholds": th, "n_paths": spec.alt_n_paths}
            sign_stack.append(Pg[0] >= mt)
            r5 = [t for t in th if abs(t["r"] - 0.05) < 1e-9]
            if r5:
                forest.append({"dimension": "generator", "label": g, "b_min": r5[0]["b_min"], "status": r5[0]["status"],
                               "lo": None, "hi": None})
        except Exception as exc:  # a generator that cannot be fitted is reported, not hidden
            alt[g] = {"error": str(exc)}
    for w0, w1 in spec.alt_windows:
        try:
            d2 = spec.data.model_copy(update={"calibration_start": w0, "calibration_end": w1})
            es_w = S.experiment_spec(d2, spec.scenario, spec.investor, spec.preferences, n_paths=spec.alt_n_paths)
            ten_w = S.get_tensor(es_w)
            ctx_w = S.get_context(es_w, ten_w, es_w.scenario.seed)
            Pw, *_ = _surface(ctx_w, assets, spec.equity, spec.bond, [0.05], bs_c, tr, (spec.main_horizon,), False, uf)
            t5 = solve_bmin(Pw[0, :, 0], bs_c, mt)
            forest.append({"dimension": "calibration window", "label": "%s..%s" % (w0[:4], w1[:4]),
                           "b_min": t5["b_min"], "status": t5["status"], "lo": None, "hi": None})
        except Exception as exc:
            forest.append({"dimension": "calibration window", "label": "%s..%s" % (w0[:4], w1[:4]), "b_min": None,
                           "status": "error: " + str(exc)[:120], "lo": None, "hi": None})
    gamma_rows = []
    ri5 = min(range(len(rs)), key=lambda i: abs(rs[i] - 0.05))
    for g in spec.gammas:
        _, CEg, *_ = _surface(ctx, assets, spec.equity, spec.bond, [rs[ri5]], bs_c, tr, (spec.main_horizon,), False,
                              uf, gamma=g)
        gamma_rows.append({"gamma": g, "b_ce": bs_c[int(np.argmax(CEg[:, 0]))]})
        forest.append({"dimension": "gamma (CE-optimal b)", "label": "gamma=%g" % g,
                       "b_min": bs_c[int(np.argmax(CEg[:, 0]))], "status": "ce_optimum", "lo": None, "hi": None})
    stack = np.array(sign_stack)
    agree = np.all(stack == stack[0], axis=0) if len(stack) > 1 else np.ones_like(stack[0], dtype=bool)

    # model-conditional allocation ranges by horizon (proxy for retirement phase; WL-12)
    phases = []
    for h in horizons:
        key = "%d|%.2f" % (h, mt)
        for row, brow in zip(thresholds[key], boot.get(key, [{}] * len(rs))):
            if abs(row["r"] - 0.04) < 1e-9:
                ri4 = rs.index(row["r"])
                phases.append({"horizon_years": h, "feasible_intervals": row["intervals"], "b_min": row["b_min"],
                               "b_min_ci": [brow.get("q05"), brow.get("q95")], "b_ce": bs[int(np.argmax(CE[:, ri4]))],
                               "status": row["status"]})

    progress("summarising", 0.95)
    warnings = S.common_warnings(u, ten)
    if spec.investor.horizon_years * 12 > len(u.real):
        pass
    return {
        "kind": "frontier", "r": rs, "b": bs, "horizons": list(horizons), "targets": list(spec.targets),
        "main_horizon": spec.main_horizon, "main_target": mt, "bond": spec.bond, "equity": spec.equity,
        "rebalancer": spec.rebalancer,
        "p_success": {str(h): S.to_list(P[hidx[h]]) for h in horizons},
        "p_lo": {str(h): S.to_list(lo[hidx[h]]) for h in horizons},
        "p_hi": {str(h): S.to_list(hi[hidx[h]]) for h in horizons},
        "p_until_death": S.to_list(UD), "ce": S.to_list(CE, 2), "ce_se": S.to_list(CE_SE, 2),
        "unmet_mean": S.to_list(UNMET, 2), "unmet_cvar95": S.to_list(CVAR, 2),
        "thresholds": thresholds, "threshold_bootstrap": boot, "breakpoints": breakpoints,
        "max_sustainable": max_r, "max_sustainable_boot": maxr_boot, "optima": optima, "details": details,
        "bond_spectrum": spectrum, "alt_generators": alt, "forest": forest, "gamma_optima": gamma_rows,
        "agreement": {"r": rs_c, "b": bs_c, "agree": agree.astype(int).tolist(),
                      "n_models": int(len(stack)), "feasible_all": np.all(stack, axis=0).astype(int).tolist()},
        "phases": phases, "universe": S.universe_block(u), "scenario": S.scenario_block(ten), "n_paths": N,
        "ci_method": "Wilson score per cell (iid MC conditional on the fitted model); b_min by joint path bootstrap "
                     "of the surface (%d replicates); parameter/model uncertainty shown separately" % spec.n_boot,
        "definitions": {"success": "no unmet desired real withdrawal through year T (fixed horizon, financial)",
                        "until_death": "1 - E[S(first shortfall)] with SSA period survival",
                        "b": "share in %s; remainder in %s; %s rebalancing" % (
                            panel.asset_label(spec.bond), panel.asset_label(spec.equity), spec.rebalancer),
                        "r": "initial annual real withdrawal / initial portfolio, held fixed in real terms"},
        "warnings": warnings, "timings": {},
        "summary": {"n_paths": N, "universe": u.name, "generator": spec.scenario.generator,
                    "breakpoint_90": breakpoints.get("%.2f" % mt), "main_horizon": spec.main_horizon},
    }


def trace_cell(spec: FrontierSpec, r: float, b: float, path: int) -> dict[str, Any]:
    es = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences)
    ten = S.get_tensor(es)
    ctx = S.get_context(es, ten, es.scenario.seed)
    assets = ten.assets
    w = np.zeros(len(assets))
    w[assets.index(spec.equity)] += 1 - b
    w[assets.index(spec.bond)] += b
    out = S.run(ctx, w, S.strategy(spec.rebalancer, spec.costs), rate=r, record=True, trace=path,
                util_floor=spec.preferences.util_floor_annual)
    return trace_payload(out, ctx, assets, path)


def trace_payload(out: ledger.LedgerOutput, ctx: Any, assets: tuple[str, ...], path: int) -> dict[str, Any]:
    t = out.trace
    Y = out.cons_y.shape[1]
    j = path
    return {"path": j, "assets": list(assets), "ages": (ctx.investor.start_age + np.arange(Y + 1)).tolist(),
            "wealth_y": S.to_list(out.wealth_y[j], 2), "consumption_y": S.to_list(out.cons_y[j], 2),
            "unmet_y": S.to_list(out.unmet_y[j], 2), "desired_y": S.to_list(out.desired_y[j], 2),
            "first_shortfall_month": int(out.first_shortfall[j]),
            "monthly": {"pre_weights": S.to_list(t["pre"], 5), "post_weights": S.to_list(t["post"], 5),
                        "target": S.to_list(t["tgt"], 5), "trades": S.to_list(t["trade"], 2),
                        "cost": S.to_list(t["cost"], 2), "desired_draw": S.to_list(t["flow"][:, 0], 2),
                        "funded_draw": S.to_list(t["flow"][:, 1], 2), "contribution": S.to_list(t["flow"][:, 2], 2),
                        "other_income": S.to_list(t["flow"][:, 3], 2), "reason": t["reason"].tolist(),
                        "wealth_post_trade": S.to_list(t["wealth"], 2)},
            "reasons": ledger.REASONS}
