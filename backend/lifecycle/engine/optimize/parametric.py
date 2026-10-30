"""Parametric dynamic policies optimised by simulation on common random numbers (train/test split).

Growth share alpha_t = clip(theta0 + theta1 (age - 65)/10 + theta2 (ln x_t - ln 25) + theta3 1{regime>0}),
x_t = investable wealth in years of current spending. The amortised spending rule's real rate
can be optimised jointly. theta is fitted on seed-set A and reported on seed-set B.
"""
from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize

from lifecycle.engine.lifecycle import policies as pol
from lifecycle.engine.lifecycle.simulator import Context, Spending, ce_annual, evaluate


@dataclass
class ParametricFit:
    theta: NDArray[np.float64]
    amort_rate: float | None
    ce_train: float
    ce_test: float
    se_test: float
    evaluations: int
    overfit_gap: float      # (CE_train - CE_test) / CE_test


def _simplex(z0: NDArray[np.float64]) -> NDArray[np.float64]:
    """Initial simplex with steps sized to the policy parameters (0.1 in shares and slopes)."""
    pts = [z0]
    for i in range(len(z0)):
        z = z0.copy()
        z[i] += 0.1 if i > 0 or z0[0] < 0.9 else -0.1
        pts.append(z)
    return np.array(pts)


def _policy(theta: NDArray[np.float64], risky: NDArray[np.float64], safe: NDArray[np.float64],
            months: int) -> pol.WeightPolicy:
    return pol.parametric(theta, risky, safe, months)


def fit_parametric(train: Context, test: Context, risky: NDArray[np.float64], safe: NDArray[np.float64],
                   spending: Spending, use_regime: bool = False, optimise_spending: bool = False,
                   l2: float = 1e-4, starts: list[list[float]] | None = None, max_iter: int = 90) -> ParametricFit:
    gamma = train.prefs.gamma
    n_theta = 4 if use_regime else 3
    evals = {"n": 0}

    def unpack(z: NDArray[np.float64]) -> tuple[NDArray[np.float64], Spending]:
        theta = np.zeros(4)
        theta[:n_theta] = z[:n_theta]
        sp = spending
        if optimise_spending:
            sp = replace(spending, amort_rate=float(np.clip(z[n_theta], -0.02, 0.08)))
        return theta, sp

    def objective(z: NDArray[np.float64]) -> float:
        evals["n"] += 1
        theta, sp = unpack(z)
        out = evaluate(train, _policy(theta, risky, safe, train.months), sp)
        ce, _ = ce_annual(out, gamma)
        return -ce / 1000.0 + l2 * float(np.sum(theta[1:] ** 2))

    if starts is None:
        starts = [[0.6, 0.0, 0.0], [0.4, -0.1, 0.1], [0.8, -0.2, 0.0]]
    best = None
    for s0 in starts:
        z0 = list(s0[:n_theta]) + [0.0] * max(0, n_theta - len(s0))
        if optimise_spending:
            z0 = z0 + [spending.amort_rate]
        res = minimize(objective, np.array(z0, dtype=float), method="Nelder-Mead",
                       options={"xatol": 5e-3, "fatol": 2e-3, "maxiter": max_iter,
                                "initial_simplex": _simplex(np.array(z0, dtype=float))})
        if best is None or res.fun < best.fun:
            best = res
    assert best is not None
    theta, sp = unpack(best.x)
    out_tr = evaluate(train, _policy(theta, risky, safe, train.months), sp)
    out_te = evaluate(test, _policy(theta, risky, safe, test.months), sp)
    ce_tr, _ = ce_annual(out_tr, gamma)
    ce_te, se_te = ce_annual(out_te, gamma)
    return ParametricFit(theta, sp.amort_rate if optimise_spending else None, ce_tr, ce_te, se_te, evals["n"],
                         (ce_tr - ce_te) / ce_te if ce_te > 0 else float("nan"))


def best_constant_share(ctx: Context, risky: NDArray[np.float64], safe: NDArray[np.float64], spending: Spending,
                        shares: NDArray[np.float64] | None = None) -> tuple[float, float, list[tuple[float, float]]]:
    """Grid search the growth share of a constant mix (0..100% in 10% steps by default)."""
    grid = np.linspace(0, 1, 11) if shares is None else shares
    gamma = ctx.prefs.gamma
    table = []
    for a in grid:
        w = a * risky + (1 - a) * safe
        out = evaluate(ctx, pol.constant_mix(w, ctx.months), spending)
        ce, _ = ce_annual(out, gamma)
        table.append((float(a), ce))
    best = max(table, key=lambda r: r[1])
    return best[0], best[1], table


def fit_glidepath(train: Context, risky: NDArray[np.float64], safe: NDArray[np.float64],
                  spending: Spending) -> tuple[float, float, float]:
    """Coarse-to-fine search over linear glidepaths share = theta0 + theta1 (age-65)/10."""
    gamma = train.prefs.gamma
    best = (0.0, 0.0, -np.inf)
    a0, ce0, _ = best_constant_share(train, risky, safe, spending)
    best = (a0, 0.0, ce0)
    for t0 in np.clip(a0 + np.array([-0.2, -0.1, 0.0, 0.1, 0.2]), 0, 1):
        for t1 in [-0.3, -0.2, -0.1, 0.1]:
            out = evaluate(train, pol.linear_glidepath(train.investor.start_age, train.months, t0, t1, risky, safe),
                           spending)
            ce, _ = ce_annual(out, gamma)
            if ce > best[2]:
                best = (float(t0), float(t1), ce)
    return best
