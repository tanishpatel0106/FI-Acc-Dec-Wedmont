"""Grid dynamic programming on the reduced problem (brief 4.6), annual decisions.

State: normalised cash-on-hand x = X / P (P = permanent income while working, frozen at
retirement) and the regime s. Under CRRA and homothetic income the value function scales
as P^{1-gamma}, so
    V_t(x, s) = max_{c, w} u(c) + beta s_{t+1} E[G'^{1-gamma} V_{t+1}(x', s')] + beta eta (1-s_{t+1}) E[b(a R_w)]
    x' = a R_w / G' + y',  a = x - c.
Expectations use Markov-chain nodes per starting regime (or Gauss-Hermite nodes for the
Merton check). The continuation value is computed once per (savings a, weight w, regime)
and maximised over the 21-point simplex grid, then consumption is refined by golden section.
Value functions are interpolated in certainty-equivalent space ((1-gamma) V)^(1/(1-gamma)),
which is close to linear in x.
"""
from dataclasses import dataclass

import numpy as np
from numba import njit, prange
from numpy.typing import NDArray


@njit(cache=True)
def _to_t(v, gamma):
    if gamma == 1.0:
        return np.exp(v)
    z = (1.0 - gamma) * v
    if z <= 1e-300:
        z = 1e-300
    return z ** (1.0 / (1.0 - gamma))


@njit(cache=True)
def _from_t(tv, gamma):
    if tv <= 1e-300:
        tv = 1e-300
    if gamma == 1.0:
        return np.log(tv)
    return tv ** (1.0 - gamma) / (1.0 - gamma)


@njit(cache=True)
def _u(c, gamma):
    if c <= 1e-300:
        c = 1e-300
    if gamma == 1.0:
        return np.log(c)
    return c ** (1.0 - gamma) / (1.0 - gamma)


@njit(cache=True)
def _interp(xg, yg, x):
    n = xg.shape[0]
    if x <= xg[0]:
        return yg[0]
    if x >= xg[n - 1]:
        slope = (yg[n - 1] - yg[n - 2]) / (xg[n - 1] - xg[n - 2])
        return yg[n - 1] + slope * (x - xg[n - 1])
    i = np.searchsorted(xg, x) - 1
    w = (x - xg[i]) / (xg[i + 1] - xg[i])
    return yg[i] * (1.0 - w) + yg[i + 1] * w


@njit(parallel=True, cache=True)
def _continuation(a_grid, wgrid, Rn, sn, Gn, yn, pm, xg, tv_next, gamma, beta_s, beq_w, kshift, xfloor, out_q):
    K = Rn.shape[0]
    M = Rn.shape[1]
    A = Rn.shape[2]
    nw = wgrid.shape[0]
    na = a_grid.shape[0]
    for idx in prange(K * nw):
        s = idx // nw
        wi = idx % nw
        rp = np.zeros(M)
        for m in range(M):
            acc = 0.0
            for k in range(A):
                acc += wgrid[wi, k] * Rn[s, m, k]
            rp[m] = acc
        for ia in range(na):
            a = a_grid[ia]
            acc = 0.0
            for m in range(M):
                G = Gn[s, m]
                xn = a * rp[m] / G + yn[s, m]
                if xn < xfloor:
                    xn = xfloor
                v = _from_t(_interp(xg, tv_next[sn[s, m]], xn), gamma)
                acc += pm[s, m] * beta_s * G ** (1.0 - gamma) * v
                if beq_w > 0.0:
                    acc += pm[s, m] * beq_w * _u(a * rp[m] + kshift, gamma)
            out_q[s, wi, ia] = acc


@njit(parallel=True, cache=True)
def _consume(xg, a_grid, tq, gamma, c_floor, out_c, out_tv):
    K = tq.shape[0]
    nx = xg.shape[0]
    gr = (np.sqrt(5.0) - 1.0) / 2.0
    for idx in prange(K * nx):
        s = idx // nx
        ix = idx % nx
        x = xg[ix]
        lo = a_grid[0]
        hi = x - c_floor
        if hi <= lo:
            c = max(x - lo, c_floor)
            out_c[s, ix] = c
            out_tv[s, ix] = _to_t(_u(c, gamma) + _from_t(_interp(a_grid, tq[s], lo), gamma), gamma)
            continue
        a1 = hi - gr * (hi - lo)
        a2 = lo + gr * (hi - lo)
        f1 = _u(x - a1, gamma) + _from_t(_interp(a_grid, tq[s], a1), gamma)
        f2 = _u(x - a2, gamma) + _from_t(_interp(a_grid, tq[s], a2), gamma)
        for _ in range(60):
            if f1 < f2:
                lo = a1
                a1 = a2
                f1 = f2
                a2 = lo + gr * (hi - lo)
                f2 = _u(x - a2, gamma) + _from_t(_interp(a_grid, tq[s], a2), gamma)
            else:
                hi = a2
                a2 = a1
                f2 = f1
                a1 = hi - gr * (hi - lo)
                f1 = _u(x - a1, gamma) + _from_t(_interp(a_grid, tq[s], a1), gamma)
        a = 0.5 * (lo + hi)
        # corner: saving nothing
        f_corner = _u(x - a_grid[0], gamma) + _from_t(_interp(a_grid, tq[s], a_grid[0]), gamma)
        fa = _u(x - a, gamma) + _from_t(_interp(a_grid, tq[s], a), gamma)
        if f_corner > fa:
            a = a_grid[0]
            fa = f_corner
        out_c[s, ix] = x - a
        out_tv[s, ix] = _to_t(fa, gamma)


@dataclass
class DPProblem:
    ages: NDArray[np.float64]           # decision ages, length T (annual)
    surv: NDArray[np.float64]           # s_{t+1}: P(alive at t+1 | alive at t), length T
    gamma: float
    beta: float                         # annual
    eta: float
    bequest_shift: float                # normalised units
    wgrid: NDArray[np.float64]          # (n_w, A)
    # nodes per phase: index 0 = working (next year still working), 1 = retired
    R_nodes: NDArray[np.float64]        # (K, M, A) gross annual real returns
    s_next: NDArray[np.int64]           # (K, M)
    probs: NDArray[np.float64]          # (K, M)
    G_work: NDArray[np.float64]         # (T, K, M) permanent income growth while working
    y_work: NDArray[np.float64]         # (K, M) transitory income factor
    pension: float                      # normalised pension after retirement
    retire_index: int                   # first decision year in retirement
    c_floor: float = 1e-3
    n_x: int = 200
    x_max: float = 200.0


@dataclass
class DPSolution:
    ages: NDArray[np.float64]
    x_grid: NDArray[np.float64]
    a_grid: NDArray[np.float64]
    wgrid: NDArray[np.float64]
    consumption: NDArray[np.float64]    # (T, K, n_x)
    weight_index: NDArray[np.int64]     # (T, K, n_x) optimal weight at savings a = x - c
    value_ce: NDArray[np.float64]       # (T, K, n_x) value in CE space
    gamma: float

    def weights(self, t: int, s: int) -> NDArray[np.float64]:
        return self.wgrid[self.weight_index[t, s]]


def solve(p: DPProblem) -> DPSolution:
    T = len(p.ages)
    K, M, A = p.R_nodes.shape
    xg = np.exp(np.linspace(np.log(max(p.c_floor, 1e-4)), np.log(p.x_max), p.n_x))
    a_grid = np.concatenate([[1e-6], np.exp(np.linspace(np.log(1e-3), np.log(p.x_max), p.n_x - 1))])
    cons = np.zeros((T, K, p.n_x))
    widx = np.zeros((T, K, p.n_x), dtype=np.int64)
    tv = np.zeros((T, K, p.n_x))
    # terminal year: consume everything
    for s in range(K):
        cons[T - 1, s] = xg
        tv[T - 1, s] = xg
        widx[T - 1, s] = 0
    q = np.zeros((K, p.wgrid.shape[0], len(a_grid)))
    for t in range(T - 2, -1, -1):
        working_next = (t + 1) < p.retire_index
        if working_next:
            Gn = p.G_work[t]
            yn = p.y_work
        else:
            Gn = np.ones((K, M))
            yn = np.full((K, M), p.pension)
        beta_s = p.beta * p.surv[t]
        beq_w = p.beta * p.eta * (1.0 - p.surv[t])
        xfloor = max(p.c_floor, 1e-4)
        _continuation(a_grid, p.wgrid, p.R_nodes, p.s_next, Gn, yn, p.probs, xg, tv[t + 1], p.gamma, beta_s, beq_w,
                      p.bequest_shift, xfloor, q)
        best = np.argmax(q, axis=1)                          # (K, n_a)
        qstar = np.take_along_axis(q, best[:, None, :], axis=1)[:, 0, :]
        tq = np.empty_like(qstar)
        for s in range(K):
            for i in range(len(a_grid)):
                tq[s, i] = _to_t(qstar[s, i], p.gamma)
        c_t = np.zeros((K, p.n_x))
        tv_t = np.zeros((K, p.n_x))
        _consume(xg, a_grid, tq, p.gamma, p.c_floor, c_t, tv_t)
        cons[t] = c_t
        tv[t] = tv_t
        for s in range(K):
            a_opt = np.maximum(xg - c_t[s], a_grid[0])
            pos = np.clip(np.searchsorted(a_grid, a_opt), 0, len(a_grid) - 1)
            widx[t, s] = best[s, pos]
    return DPSolution(p.ages, xg, a_grid, p.wgrid, cons, widx, tv, p.gamma)


def nodes_from_paths(annual_gross: NDArray[np.float64], start_regime: NDArray[np.int64],
                     end_regime: NDArray[np.int64], K: int, max_nodes: int = 600,
                     seed: int = 0) -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.float64]]:
    """Equal-probability Markov-chain nodes per starting regime from simulated one-year draws."""
    rng = np.random.default_rng(seed)
    A = annual_gross.shape[1]
    R = np.ones((K, max_nodes, A))
    sn = np.zeros((K, max_nodes), dtype=np.int64)
    pm = np.zeros((K, max_nodes))
    for s in range(K):
        idx = np.flatnonzero(start_regime == s)
        if len(idx) == 0:
            idx = np.arange(len(start_regime))
        pick = idx if len(idx) <= max_nodes else rng.choice(idx, max_nodes, replace=False)
        m = len(pick)
        R[s, :m] = annual_gross[pick]
        sn[s, :m] = end_regime[pick]
        pm[s, :m] = 1.0 / m
    return R, sn, pm


def gauss_hermite_lognormal(mu: float, sigma: float, rf: float, n: int = 30) -> tuple[NDArray[np.float64],
                                                                                       NDArray[np.float64]]:
    """Two-asset nodes: risky gross return exp(N(mu - sigma^2/2, sigma^2)) and a riskless gross 1+rf."""
    x, w = np.polynomial.hermite_e.hermegauss(n)
    w = w / w.sum()
    risky = np.exp(mu - 0.5 * sigma ** 2 + sigma * x)
    return np.column_stack([risky, np.full(n, 1.0 + rf)]), w


def simulate_policy(sol: DPSolution, R_paths: NDArray[np.float64], regime: NDArray[np.int64],
                    G_paths: NDArray[np.float64], y_paths: NDArray[np.float64],
                    x0: float) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Apply the DP policy to annual paths. Returns consumption (N,T), weights (N,T,A), x (N,T) normalised."""
    N, T, A = R_paths.shape
    T = min(T, len(sol.ages))
    c = np.zeros((N, T))
    w = np.zeros((N, T, A))
    xs = np.zeros((N, T))
    x = np.full(N, x0)
    for t in range(T):
        xs[:, t] = x
        ct = np.zeros(N)
        wt = np.zeros((N, A))
        for s in range(sol.consumption.shape[1]):
            m = regime[:, t] == s
            if not np.any(m):
                continue
            ct[m] = np.interp(x[m], sol.x_grid, sol.consumption[t, s])
            wt[m] = sol.wgrid[sol.weight_index[t, s][np.clip(np.searchsorted(sol.x_grid, x[m]), 0,
                                                                  len(sol.x_grid) - 1)]]
        ct = np.minimum(np.maximum(ct, 1e-6), x)
        c[:, t] = ct
        w[:, t] = wt
        rp = np.sum(wt * R_paths[:, t], axis=1)
        x = (x - ct) * rp / G_paths[:, t] + y_paths[:, t]
    return c, w, xs
