"""Grid-DP experiment on the reduced three-asset problem (US equity, 10Y Treasury, T-bills) x regimes.

The DP is solved at annual frequency; the DP policy and the benchmark are compared on the same
annualised scenario paths (compounded from the monthly tensor) so the comparison is like-for-like.
"""
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from lifecycle.engine.lifecycle import mortality
from lifecycle.engine.lifecycle.income import age_profile
from lifecycle.engine.lifecycle.utility import ce_with_se, paired_delta_ce
from lifecycle.engine.optimize import grid_dp
from lifecycle.engine.optimize.static import simplex_grid
from lifecycle.runs import context as C
from lifecycle.runs.spec import ExperimentSpec

REDUCED = ("us_eq", "ust_10y", "tbill")
Progress = Callable[[str, float], None]


def _annualise(real: np.ndarray, regime: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    N, T, A = real.shape
    Y = T // 12
    g = np.prod(1.0 + real[:, : Y * 12].reshape(N, Y, 12, A), axis=2)
    start = regime[:, : Y * 12: 12]
    end = regime[:, 11: Y * 12: 12]
    return g, start, end


def _income_nodes(rng: np.random.Generator, R: np.ndarray, ages: np.ndarray, profile: str, sigma_u: float,
                  sigma_eps: float, rho: float) -> tuple[np.ndarray, np.ndarray]:
    K, M, _ = R.shape
    z_e = np.log(R[:, :, 0])
    z_e = (z_e - z_e.mean()) / max(z_e.std(), 1e-12)
    z = rng.standard_normal((K, M))
    u = sigma_u * (rho * z_e + np.sqrt(max(1 - rho ** 2, 0.0)) * z) - 0.5 * sigma_u ** 2
    df = age_profile(ages + 1.0, profile) - age_profile(ages, profile)
    G = np.exp(df[:, None, None] + u[None, :, :])
    eps = sigma_eps * rng.standard_normal((K, M)) - 0.5 * sigma_eps ** 2
    return G, np.exp(eps)


def build_problem(spec: ExperimentSpec, grid_divisions: int = 5, n_nodes: int = 600,
                  K_override: int | None = None, model: Any = None) -> tuple[grid_dp.DPProblem, dict[str, Any]]:
    inv = spec.investor
    pref = spec.preferences
    K = spec.scenario.k_regimes if spec.scenario.generator == "markov_switching" else 1
    if K_override is not None:
        K = K_override
    years = int(round(inv.max_age - inv.start_age))
    ages = inv.start_age + np.arange(years, dtype=float)
    q = C.q_vector(spec)
    surv = np.empty(years)
    for t in range(years):
        a = min(int(np.floor(ages[t])), len(q) - 1)
        surv[t] = (1.0 - q[a]) if inv.mortality else 1.0
    retire_index = max(int(round(inv.retirement_age - inv.start_age)), 0)
    # one-year joint draws per starting regime from the fitted scenario model
    rs = []
    starts = []
    ends = []
    for s in range(K):
        if model is None:
            ten = C.tensor(spec, seed=spec.scenario.seed + 101 + s, n_paths=n_nodes,
                           start_regime=s if K > 1 else None)
        else:
            from lifecycle.engine.scenarios import generate

            ten = generate(model, C.universe(spec).assets, n_nodes, 12, spec.scenario.seed + 101 + s,
                           s if K > 1 else None)
        cols = [ten.assets.index(a) for a in REDUCED]
        g, st, en = _annualise(ten.real_returns[:, :12, cols], ten.regime[:, :12])
        rs.append(g[:, 0])
        starts.append(np.full(len(g), s) if K > 1 else np.zeros(len(g), dtype=np.int64))
        ends.append(np.minimum(en[:, 0], K - 1) if K > 1 else np.zeros(len(g), dtype=np.int64))
    R_all = np.concatenate(rs)
    R_nodes, s_next, probs = grid_dp.nodes_from_paths(R_all, np.concatenate(starts), np.concatenate(ends), K,
                                                      max_nodes=n_nodes, seed=spec.scenario.seed)
    rng = np.random.default_rng(spec.scenario.seed + 7)
    G, ytr = _income_nodes(rng, R_nodes, ages, inv.income_profile, inv.sigma_u, inv.sigma_eps, inv.rho_ye)
    if retire_index > 0:
        unit = inv.income
        if inv.pension is None:
            pension_norm = inv.replacement_rate
        else:
            growth = np.exp(age_profile(np.array([inv.retirement_age]), inv.income_profile)[0]
                            - age_profile(np.array([inv.start_age]), inv.income_profile)[0])
            pension_norm = inv.pension / (inv.income * growth)
        x0 = inv.initial_wealth / unit + 1.0
    else:
        pension = inv.pension if inv.pension is not None else inv.replacement_rate * inv.income
        unit = pension if pension > 0 else max(inv.initial_wealth / 25.0, 1.0)
        pension_norm = pension / unit
        x0 = (inv.initial_wealth + pension) / unit
    problem = grid_dp.DPProblem(
        ages=ages, surv=surv, gamma=pref.gamma, beta=pref.beta_annual, eta=pref.eta,
        bequest_shift=pref.bequest_shift / unit, wgrid=simplex_grid(3, grid_divisions), R_nodes=R_nodes,
        s_next=s_next, probs=probs, G_work=G, y_work=ytr, pension=float(pension_norm), retire_index=retire_index,
        c_floor=pref.c_min / unit, x_max=max(200.0, 4.0 * x0))
    return problem, {"unit": unit, "x0": x0, "K": K, "pension_norm": pension_norm}


def _simulate_income_paths(spec: ExperimentSpec, R: np.ndarray, rng: np.random.Generator,
                           retire_index: int, pension_norm: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    inv = spec.investor
    N, Y, _ = R.shape
    ages = inv.start_age + np.arange(Y, dtype=float)
    z_e = np.log(R[:, :, 0])
    z_e = (z_e - z_e.mean()) / max(z_e.std(), 1e-12)
    u = inv.sigma_u * (inv.rho_ye * z_e + np.sqrt(max(1 - inv.rho_ye ** 2, 0)) * rng.standard_normal((N, Y))) \
        - 0.5 * inv.sigma_u ** 2
    df = age_profile(ages + 1.0, inv.income_profile) - age_profile(ages, inv.income_profile)
    G = np.exp(df[None, :] + u)
    y = np.exp(inv.sigma_eps * rng.standard_normal((N, Y)) - 0.5 * inv.sigma_eps ** 2)
    for t in range(Y):
        if t + 1 >= retire_index:
            G[:, t] = 1.0
            y[:, t] = pension_norm
    level = np.ones((N, Y))
    for t in range(1, Y):
        level[:, t] = level[:, t - 1] * G[:, t - 1]
    return G, y, level


def _utilities(c_norm: np.ndarray, level: np.ndarray, unit: float, disc: np.ndarray, gamma: float) -> np.ndarray:
    c = np.maximum(c_norm * level * unit / 1000.0, 1e-9)
    if gamma == 1.0:
        u = np.log(c)
    else:
        u = c ** (1 - gamma) / (1 - gamma)
    return (u * disc[None, : c.shape[1]]).sum(axis=1)


def _benchmark_annual(R: np.ndarray, G: np.ndarray, y: np.ndarray, x0: float, w: np.ndarray, retire_index: int,
                      savings_rate: float, rate: float, pension_norm: float, c_floor: float) -> np.ndarray:
    N, Y, _ = R.shape
    c = np.zeros((N, Y))
    x = np.full(N, x0)
    wr = np.full(N, np.nan)
    for t in range(Y):
        if t < retire_index:
            ct = np.minimum((1 - savings_rate) * y[:, t - 1] if t > 0 else np.full(N, 1 - savings_rate), x)
        else:
            if t == retire_index:
                wr = (x - pension_norm) * rate
            ct = np.minimum(np.maximum(wr, 0) + pension_norm, x)
        ct = np.maximum(ct, np.minimum(c_floor, x))
        c[:, t] = ct
        rp = R[:, t] @ w
        x = (x - ct) * rp / G[:, t] + y[:, t]
    return c


def run_dp(spec: ExperimentSpec, progress: Progress) -> dict[str, Any]:
    t0 = time.time()
    progress("generating_scenarios", 0.05)
    divisions = int(spec.policy.params.get("grid_divisions", 5))
    problem, meta = build_problem(spec, divisions)
    progress("optimising", 0.2)
    sol = grid_dp.solve(problem)
    t_solve = time.time() - t0
    progress("simulating", 0.7)
    ten = C.tensor(spec)
    cols = [ten.assets.index(a) for a in REDUCED]
    R, reg, _ = _annualise(ten.real_returns[:, :, cols], ten.regime)
    K = meta["K"]
    reg = np.minimum(reg, K - 1) if K > 1 else np.zeros_like(reg)
    rng = np.random.default_rng(spec.scenario.seed + 11)
    G, y, level = _simulate_income_paths(spec, R, rng, problem.retire_index, meta["pension_norm"])
    c_dp, w_dp, xs = grid_dp.simulate_policy(sol, R, reg, G, y, meta["x0"])
    Y = c_dp.shape[1]
    beta = spec.preferences.beta_annual
    S = np.concatenate([[1.0], np.cumprod(problem.surv)])[:Y]
    disc = beta ** np.arange(Y) * S
    gamma = spec.preferences.gamma
    u_dp = _utilities(c_dp, level[:, :Y], meta["unit"], disc, gamma)
    w6040 = np.array([0.6, 0.4, 0.0])
    c_b = _benchmark_annual(R[:, :Y], G[:, :Y], y[:, :Y], meta["x0"], w6040, problem.retire_index,
                            spec.investor.savings_rate, spec.policy.withdrawal_rate, meta["pension_norm"],
                            problem.c_floor)
    u_b = _utilities(c_b, level[:, :Y], meta["unit"], disc, gamma)
    sd = float(disc.sum())
    ce_dp, se_dp = ce_with_se(u_dp, gamma, sd)
    ce_b, se_b = ce_with_se(u_b, gamma, sd)
    d, dse = paired_delta_ce(u_dp, u_b, gamma, sd)
    progress("summarising", 0.9)
    surfaces = policy_surfaces(sol, meta, problem)
    ages = problem.ages[:Y]
    qs = spec.outputs.quantiles
    wealth_dollars = xs * level[:, :Y] * meta["unit"]
    return {
        "kind": "dp",
        "ages": ages.tolist(),
        "assets": list(REDUCED),
        "ce": {"policy": {"ce": ce_dp * 1000, "se": se_dp * 1000}, "benchmark": {"ce": ce_b * 1000, "se": se_b * 1000},
               "delta": {"delta": d, "se": dse, "z": d / dse if dse > 0 else 0.0, "significant": bool(abs(d) > 2 * dse)}},
        "fan": {"cash_on_hand": _q(wealth_dollars, qs), "consumption": _q(c_dp * level[:, :Y] * meta["unit"], qs),
                "benchmark_consumption": _q(c_b * level[:, :Y] * meta["unit"], qs)},
        "weights_path": {"assets": list(REDUCED), "mean": w_dp.mean(axis=0).tolist()},
        "surfaces": surfaces,
        "h1": h1_slope(surfaces),
        "policy": {"label": "grid DP (reduced 3-asset, K=%d)" % K, "type": "dp", "grid_points": int(problem.n_x),
                   "weight_grid": int(problem.wgrid.shape[0]), "nodes": int(problem.R_nodes.shape[1]),
                   "frequency": "annual", "unit_dollars": meta["unit"], "x0": meta["x0"]},
        "benchmark": {"name": "sixty_forty", "label": "60/40 with fixed real withdrawals (annual)"},
        "timings": {"solve": t_solve, "total": time.time() - t0},
        "warnings": ["DP solved at annual frequency on the reduced universe " + ", ".join(REDUCED),
                     "in-model gain: ΔCE includes optimal consumption versus a fixed-real withdrawal rule, "
                     "evaluated under the same scenario model the DP was solved on"],
        "scenario": ten.meta,
    }


def _q(arr: np.ndarray, qs: tuple[float, ...]) -> dict[str, list[float]]:
    q = np.quantile(arr, qs, axis=0)
    out = {"p%02d" % int(round(qs[i] * 100)): q[i].tolist() for i in range(len(qs))}
    out["mean"] = arr.mean(axis=0).tolist()
    return out


def policy_surfaces(sol: grid_dp.DPSolution, meta: dict[str, Any], problem: grid_dp.DPProblem) -> dict[str, Any]:
    """Optimal weights and consumption over normalised cash-on-hand, by age and regime."""
    xg = sol.x_grid
    keep = np.flatnonzero((xg >= 0.5) & (xg <= min(problem.x_max, 150)))[::3]
    T = len(sol.ages)
    age_idx = list(range(0, max(T - 1, 1), 5))
    out: dict[str, Any] = {"x": xg[keep].tolist(), "ages": [float(sol.ages[i]) for i in age_idx], "by_regime": []}
    for s in range(sol.consumption.shape[1]):
        rows = []
        for t in age_idx:
            w = sol.wgrid[sol.weight_index[t, s, keep]]
            c = sol.consumption[t, s, keep]
            working = t < problem.retire_index
            y = 1.0 if working else problem.pension
            q = (c - y) / xg[keep]
            rows.append({"age": float(sol.ages[t]), "equity": w[:, 0].tolist(), "bonds": w[:, 1].tolist(),
                         "bills": w[:, 2].tolist(), "consumption_rate": (c / xg[keep]).tolist(), "q": q.tolist()})
        out["by_regime"].append(rows)
    return out


def h1_slope(surfaces: dict[str, Any]) -> list[dict[str, float]]:
    """Slope of the optimal equity weight on the net-flow rate q at fixed age (H1 statistic)."""
    res = []
    for s, rows in enumerate(surfaces["by_regime"]):
        for r in rows:
            q = np.asarray(r["q"])
            e = np.asarray(r["equity"])
            m = np.isfinite(q) & (np.abs(q) < 1.0)
            if m.sum() < 5 or np.std(q[m]) < 1e-9:
                continue
            slope = float(np.polyfit(q[m], e[m], 1)[0])
            res.append({"regime": s, "age": r["age"], "slope": slope})
    return res


__all__ = ["run_dp", "build_problem", "policy_surfaces", "h1_slope", "mortality"]
