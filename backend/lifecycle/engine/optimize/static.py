"""Static optimisers over constant-mix weights (SLSQP / HiGHS LP), long-only with per-sleeve bounds."""
from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linprog, minimize
from sklearn.covariance import LedoitWolf


def shrunk_moments(returns: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Annualised mean and Ledoit-Wolf covariance of monthly returns."""
    mu = returns.mean(axis=0) * 12.0
    cov = LedoitWolf().fit(returns).covariance_ * 12.0
    return mu, cov


def _bounds(n: int, lower: NDArray[np.float64] | None, upper: NDArray[np.float64] | None) -> list[tuple[float, float]]:
    lo = np.zeros(n) if lower is None else lower
    hi = np.ones(n) if upper is None else upper
    return [(float(lo[i]), float(hi[i])) for i in range(n)]


def _feasible_start(n: int, bounds: list[tuple[float, float]]) -> NDArray[np.float64]:
    w = np.array([0.5 * (b[0] + b[1]) for b in bounds])
    return w / w.sum()


def mean_variance(mu: NDArray[np.float64], cov: NDArray[np.float64], risk_aversion: float,
                  lower: NDArray[np.float64] | None = None, upper: NDArray[np.float64] | None = None) -> NDArray[np.float64]:
    n = len(mu)
    b = _bounds(n, lower, upper)

    def obj(w: NDArray[np.float64]) -> float:
        return float(-(w @ mu) + 0.5 * risk_aversion * w @ cov @ w)

    def grad(w: NDArray[np.float64]) -> NDArray[np.float64]:
        return -mu + risk_aversion * cov @ w

    res = minimize(obj, _feasible_start(n, b), jac=grad, bounds=b, method="SLSQP",
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones(n)}],
                   options={"ftol": 1e-12, "maxiter": 500})
    return _clean(res.x)


def min_variance(cov: NDArray[np.float64], lower: NDArray[np.float64] | None = None,
                 upper: NDArray[np.float64] | None = None) -> NDArray[np.float64]:
    return mean_variance(np.zeros(cov.shape[0]), cov, 1.0, lower, upper)


def risk_parity(cov: NDArray[np.float64], budget: NDArray[np.float64] | None = None) -> NDArray[np.float64]:
    """Equal (or budgeted) risk contributions via the convex log-barrier formulation."""
    n = cov.shape[0]
    b = np.full(n, 1.0 / n) if budget is None else budget / budget.sum()

    def obj(y: NDArray[np.float64]) -> float:
        return float(0.5 * y @ cov @ y - b @ np.log(y))

    def grad(y: NDArray[np.float64]) -> NDArray[np.float64]:
        return cov @ y - b / y

    res = minimize(obj, np.full(n, 1.0 / np.sqrt(np.trace(cov))), jac=grad, method="L-BFGS-B",
                   bounds=[(1e-10, None)] * n, options={"maxiter": 2000})
    return _clean(res.x / res.x.sum())


def risk_contributions(w: NDArray[np.float64], cov: NDArray[np.float64]) -> NDArray[np.float64]:
    port = float(w @ cov @ w)
    return w * (cov @ w) / port


def mean_cvar(scenarios: NDArray[np.float64], alpha: float = 0.95, risk_aversion: float = 1.0,
              lower: NDArray[np.float64] | None = None, upper: NDArray[np.float64] | None = None) -> NDArray[np.float64]:
    """Rockafellar-Uryasev LP: min -E[R w] + lambda CVaR_alpha(-R w) subject to the simplex."""
    S, n = scenarios.shape
    mu = scenarios.mean(axis=0)
    lam = max(risk_aversion, 1e-9)
    # variables: w (n), zeta (1), u (S)
    c = np.concatenate([-mu, [lam], np.full(S, lam / ((1 - alpha) * S))])
    A_ub = np.hstack([-scenarios, -np.ones((S, 1)), -np.eye(S)])
    b_ub = np.zeros(S)
    A_eq = np.concatenate([np.ones(n), [0.0], np.zeros(S)])[None, :]
    bw = _bounds(n, lower, upper)
    bounds = bw + [(None, None)] + [(0, None)] * S
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=[1.0], bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError("mean-CVaR LP failed: " + str(res.message))
    return _clean(res.x[:n])


def cvar(losses: NDArray[np.float64], alpha: float = 0.95) -> float:
    q = np.quantile(losses, alpha)
    tail = losses[losses >= q]
    return float(tail.mean()) if len(tail) > 0 else float(q)


def maximize_objective(fn: Callable[[NDArray[np.float64]], float], n: int, start: NDArray[np.float64] | None = None,
                       lower: NDArray[np.float64] | None = None, upper: NDArray[np.float64] | None = None,
                       maxiter: int = 60, step: float = 0.02) -> tuple[NDArray[np.float64], float]:
    """Maximise a simulated objective (e.g. CE) over the simplex with SLSQP and finite differences."""
    b = _bounds(n, lower, upper)
    x0 = _feasible_start(n, b) if start is None else start
    base = fn(x0)
    scale = abs(base) if base != 0 else 1.0

    def neg(w: NDArray[np.float64]) -> float:
        w = np.clip(w, 0, None)
        s = w.sum()
        if s <= 0:
            return 1e6
        return -fn(w / s) / scale

    res = minimize(neg, x0, bounds=b, method="SLSQP",
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1.0}],
                   options={"maxiter": maxiter, "ftol": 1e-7, "eps": step})
    w = _clean(res.x)
    return w, fn(w)


def simplex_grid(n: int, divisions: int) -> NDArray[np.float64]:
    """All weight vectors on the simplex with step 1/divisions."""
    out: list[list[int]] = []

    def rec(prefix: list[int], remaining: int, slots: int) -> None:
        if slots == 1:
            out.append(prefix + [remaining])
            return
        for k in range(remaining + 1):
            rec(prefix + [k], remaining - k, slots - 1)

    rec([], divisions, n)
    return np.array(out, dtype=float) / divisions


def _clean(w: NDArray[np.float64]) -> NDArray[np.float64]:
    w = np.where(np.abs(w) < 1e-9, 0.0, w)
    w = np.clip(w, 0, None)
    return w / w.sum()


def resampled_frontier(returns: NDArray[np.float64], risk_aversion: float, n_resamples: int = 100,
                       seed: int = 0) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Michaud-style robustness check: average MV weights across bootstrap resamples (mean, sd)."""
    rng = np.random.default_rng(seed)
    T = returns.shape[0]
    ws = []
    for _ in range(n_resamples):
        idx = rng.integers(0, T, T)
        mu, cov = shrunk_moments(returns[idx])
        ws.append(mean_variance(mu, cov, risk_aversion))
    arr = np.array(ws)
    return arr.mean(axis=0), arr.std(axis=0)
