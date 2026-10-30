"""Brief 9.1: deterministic accounting tests."""
import numpy as np
import pytest
from helpers import run

from lifecycle.engine import fixed_income
from lifecycle.engine.lifecycle.utility import ce_from_utility, crra, paired_delta_ce


def test_zero_return_depletion_exactly_25_years():
    R = np.zeros((1, 400, 1))
    out = run(R, [1.0], w0=1_000_000.0, rate=0.04)
    assert out.deplete_month[0] == 300  # 300 months at $3,333.33 exhaust $1,000,000
    assert out.wealth_y[0, 25] == pytest.approx(0.0, abs=1e-6)
    assert out.cons_y[0, 0] == pytest.approx(40_000.0, rel=1e-12)


def test_constant_return_no_flows():
    r = 0.004
    T = 360
    R = np.full((1, T, 1), r)
    out = run(R, [1.0], w0=250_000.0, rate=0.0)
    assert out.wealth_y[0, -1] == pytest.approx(250_000.0 * (1 + r) ** T, rel=1e-10)


def test_accumulation_matches_future_value_of_annuity():
    r = 0.005
    T = 240
    y = 6_000.0
    s = 0.15
    R = np.full((1, T, 1), r)
    labor = np.full((1, T), y)
    out = run(R, [1.0], w0=0.0, retire_m=T + 1, labor=labor, savings=s)
    c = s * y
    fv = c * (1 + r) * ((1 + r) ** T - 1) / r  # contribution at start of month, then the return
    assert out.wealth_y[0, -1] == pytest.approx(fv, rel=1e-10)


def test_rebalancing_cost_equals_kappa_turnover_investable():
    R = np.array([[[0.10, -0.05], [0.0, 0.0]]])
    w = [0.5, 0.5]
    free = run(R, w, w0=100.0)
    kappa = 0.001
    cost = run(R, w, w0=100.0, kappa=kappa)
    # after month 1: W = 102.5, drifted weights 55/102.5, 47.5/102.5; turnover back to 50/50
    w_drift = np.array([55.0, 47.5]) / 102.5
    turnover = np.abs(np.array(w) - w_drift).sum()
    expected = kappa * turnover * 102.5
    assert free.wealth_y[0, -1] - cost.wealth_y[0, -1] == pytest.approx(expected, rel=1e-12)
    assert cost.turnover[0] == pytest.approx(turnover, rel=1e-12)


def test_ce_log_utility_is_exp_of_weighted_mean_log():
    c = np.array([1.0, 2.0, 3.0, 4.0])
    disc = np.array([1.0, 0.9, 0.7, 0.4])
    u = float(np.sum(disc * np.log(c)))
    assert ce_from_utility(u, 1.0, disc.sum()) == pytest.approx(np.exp(np.sum(disc * np.log(c)) / disc.sum()))


@pytest.mark.parametrize("gamma", [0.5, 2.0, 4.0, 6.0])
def test_ce_of_deterministic_stream(gamma):
    disc = 0.997 ** np.arange(120)
    c = 3.7
    u = float(np.sum(disc * crra(np.full(120, c), gamma)))
    assert ce_from_utility(u, gamma, disc.sum()) == pytest.approx(c, rel=1e-10)


def test_common_random_numbers_identical_policies_zero_delta():
    rng = np.random.default_rng(1)
    R = rng.normal(0.004, 0.04, (500, 240, 2))
    a = run(R, [0.6, 0.4], rate=0.05, gamma=4.0, c_min=0.5)
    b = run(R, [0.6, 0.4], rate=0.05, gamma=4.0, c_min=0.5)
    d, se = paired_delta_ce(a.utility, b.utility, 4.0, a.sum_disc)
    assert d == 0.0
    assert se == 0.0


@pytest.mark.parametrize("maturity", [2.0, 5.0, 10.0, 30.0])
def test_duration_convexity_within_1bp_for_25bp(maturity):
    y = 0.045
    p0 = fixed_income.price(y, y, maturity)
    dm = fixed_income.modified_duration(y, y, maturity)
    cx = fixed_income.convexity(y, y, maturity)
    for dy in (-0.0025, 0.0025):
        full = fixed_income.price(y + dy, y, maturity) / p0 - 1
        assert abs(fixed_income.approx_return(dm, cx, dy) - full) < 1e-4


def test_historical_60_40_cohorts_match_independent_loop():
    """R1 exit criterion: spreadsheet-style replication of 60/40 cohorts to 1e-8."""
    rng = np.random.default_rng(3)
    hist = np.column_stack([rng.normal(0.006, 0.045, 600), rng.normal(0.002, 0.02, 600)])
    T = 360
    starts = np.arange(0, 600 - T + 1, 12)
    R = np.stack([hist[s: s + T] for s in starts])
    out = run(R, [0.6, 0.4], w0=1_000_000.0, rate=0.04)
    for i in range(len(starts)):
        W = 1_000_000.0
        spend = 40_000.0 / 12.0
        w = np.array([0.6, 0.4])
        for t in range(T):
            c = spend if W >= spend else W
            inv = W - c
            W = inv * (1 + w @ R[i, t])
        assert out.wealth_y[i, -1] == pytest.approx(W, rel=1e-8, abs=1e-8)
