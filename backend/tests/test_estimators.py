"""Brief 9.2: estimators recover known truths."""
import numpy as np

from lifecycle.engine import dependence
from lifecycle.engine.optimize import grid_dp
from lifecycle.engine.optimize.static import simplex_grid
from lifecycle.engine.scenarios.bootstrap import politis_white_block_length
from lifecycle.engine.scenarios.markov_switching import MarkovSwitching


def test_markov_switching_recovers_parameters():
    rng = np.random.default_rng(0)
    T = 3000
    P = np.array([[0.97, 0.03], [0.05, 0.95]])
    mu = np.array([[0.01, 0.002], [-0.01, 0.008]])
    sd = np.array([[0.03, 0.002], [0.06, 0.003]])
    s = 0
    real = np.empty((T, 1))
    infl = np.empty(T)
    for t in range(T):
        if t > 0:
            s = 0 if rng.random() < P[s, 0] else 1
        real[t, 0] = np.expm1(mu[s, 0] + sd[s, 0] * rng.standard_normal())
        infl[t] = mu[s, 1] + sd[s, 1] * rng.standard_normal()
    m = MarkovSwitching(real, infl, k=2)
    # regimes are ordered by mean inflation, so regime 0 is the low-inflation state
    assert abs(m.mu[0, 0] - 0.01) < 0.004 and abs(m.mu[1, 0] + 0.01) < 0.008
    assert abs(m.mu[0, 1] - 0.002) < 0.0005 and abs(m.mu[1, 1] - 0.008) < 0.0007
    assert abs(m.P[0, 0] - 0.97) < 0.02 and abs(m.P[1, 1] - 0.95) < 0.03


def test_block_length_larger_for_persistent_series():
    rng = np.random.default_rng(1)
    e = rng.standard_normal(1200)
    ar = np.empty(1200)
    ar[0] = 0
    for t in range(1, 1200):
        ar[t] = 0.8 * ar[t - 1] + e[t]
    assert politis_white_block_length(ar) > politis_white_block_length(e)


def test_dcc_recovers_parameters():
    rng = np.random.default_rng(2)
    T = 2500
    a, b = 0.05, 0.90
    qbar = np.array([[1.0, 0.3], [0.3, 1.0]])
    Q = qbar.copy()
    z = np.empty((T, 2))
    for t in range(T):
        d = np.sqrt(np.diag(Q))
        R = Q / np.outer(d, d)
        z[t] = np.linalg.cholesky(R) @ rng.standard_normal(2)
        Q = (1 - a - b) * qbar + a * np.outer(z[t], z[t]) + b * Q
    fit = dependence.dcc_garch(z * 0.04)
    assert abs(fit["a"] - a) < 0.04
    assert abs(fit["b"] - b) < 0.1


def test_t_copula_tail_dependence_positive():
    rng = np.random.default_rng(4)
    n = 3000
    nu = 4
    g = rng.standard_normal((n, 2)) @ np.linalg.cholesky(np.array([[1, 0.5], [0.5, 1]])).T
    w = np.sqrt(nu / rng.chisquare(nu, (n, 1)))
    x = g * w
    fit = dependence.fit_t_copula(x[:, 0], x[:, 1])
    assert abs(fit["rho"] - 0.5) < 0.06
    assert fit["nu"] <= 8
    assert fit["tail_dependence"] > 0.1


def test_pelt_finds_mean_break():
    rng = np.random.default_rng(5)
    x = np.concatenate([rng.normal(0, 1, 300), rng.normal(2.0, 1, 300)])
    cps = dependence.pelt(x, min_size=30)
    assert any(abs(c - 300) <= 10 for c in cps)


def _merton_problem(n_x: int) -> grid_dp.DPProblem:
    rf, sig, prem = 0.02, 0.2, 0.04
    nodes, w = grid_dp.gauss_hermite_lognormal(np.log(1 + rf + prem), sig, rf, 30)
    T = 40
    return grid_dp.DPProblem(ages=np.arange(T) + 40.0, surv=np.ones(T), gamma=4.0, beta=0.97, eta=0.0,
                             bequest_shift=0.0, wgrid=simplex_grid(2, 20), R_nodes=nodes[None],
                             s_next=np.zeros((1, 30), dtype=np.int64), probs=w[None], G_work=np.ones((T, 1, 30)),
                             y_work=np.zeros((1, 30)), pension=0.0, retire_index=0, c_floor=1e-4, n_x=n_x,
                             x_max=200)


def test_merton_benchmark_recovered_by_dp():
    sol = grid_dp.solve(_merton_problem(200))
    ix = np.searchsorted(sol.x_grid, [1.0, 10.0, 50.0])
    eq = sol.wgrid[sol.weight_index[0, 0, ix]][:, 0]
    assert np.allclose(eq, 0.04 / (4.0 * 0.04), atol=0.051)


def test_dp_grid_refinement_stable():
    coarse = grid_dp.solve(_merton_problem(100))
    fine = grid_dp.solve(_merton_problem(200))
    x = np.array([2.0, 10.0, 40.0])
    c1 = np.interp(x, coarse.x_grid, coarse.consumption[0, 0]) / x
    c2 = np.interp(x, fine.x_grid, fine.consumption[0, 0]) / x
    assert np.max(np.abs(c1 - c2)) < 0.002
