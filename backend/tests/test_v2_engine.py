"""v2 holdings ledger, trading policies, PIT signals and threshold solver (brief section 13.1)."""
import numpy as np
import pytest

from lifecycle.engine.lifecycle import ledger
from lifecycle.studies.common import success, until_death_success, wilson
from lifecycle.studies.frontier import solve_bmin


def _cfg(T, A=2, w=(0.6, 0.4), K=1, **kw):
    sched = np.zeros((T, K, A))
    sched[:, :, :] = np.asarray(w)
    base = dict(w0=1e6, retire_m=0, spend_mode=ledger.SP_FIXED_REAL, rate=0.04, savings_rate=0.0, sched=sched,
                trading=ledger.TradingSpec(mode="calendar", cadence_months=12), disc=np.ones(T), beq=np.zeros(T),
                record_years=True)
    base.update(kw)
    return ledger.LedgerConfig(**base)


def _sim(R, cfg, dec=None, labor=None):
    N, T, _ = R.shape
    dec = np.zeros((N, T), dtype=np.int64) if dec is None else dec
    z = np.zeros((N, T)) if labor is None else labor
    return ledger.simulate(R, dec, z, np.zeros((N, T)), cfg)


def independent_loop(R, w, rate, w0, cadence, comm_bps, spread_bps):
    """Spreadsheet-style holdings loop: proportional withdrawals, annual reset, cost on traded notional."""
    T, A = R.shape
    h = np.array(w) * w0
    spend = None
    unmet = 0.0
    fee = (comm_bps + spread_bps) / 1e4
    for t in range(T):
        W = h.sum()
        if t == 0:
            spend = rate * W
        d = spend / 12
        f = min(d, W)
        unmet += d - f
        if f > 0 and W > 0:
            sell = f * h / W
            h = h - sell
            c = np.abs(sell).sum() * fee
            W2 = h.sum()
            if W2 > 0:
                h = h - c * h / W2
        W = h.sum()
        if t > 0 and t % cadence == 0 and W > 0:
            c = 0.0
            for _ in range(4):
                c = np.abs(np.array(w) * (W - c) - h).sum() * fee
            h = np.array(w) * (W - c)
        h = np.maximum(h * (1 + R[t]), 0)
    return h.sum(), unmet


def test_ledger_matches_independent_loop():
    rng = np.random.default_rng(1)
    T = 120
    R = rng.normal(0.005, 0.04, (3, T, 2))
    cfg = _cfg(T, trading=ledger.TradingSpec(mode="calendar", cadence_months=12, commission_bps=2, half_spread_bps=3))
    out = _sim(R, cfg)
    for j in range(3):
        wend, unmet = independent_loop(R[j], (0.6, 0.4), 0.04, 1e6, 12, 2, 3)
        assert out.terminal[j] == pytest.approx(wend, rel=1e-10)
        assert out.unmet[j] == pytest.approx(unmet, abs=1e-6)


def test_no_phantom_consumption_and_no_negative_wealth():
    T = 60
    R = np.full((1, T, 2), -0.05)  # collapsing markets
    out = _sim(R, _cfg(T, rate=0.30))
    assert out.terminal[0] >= 0
    assert out.first_shortfall[0] >= 0
    assert out.unmet[0] > 0
    # funded consumption never exceeds desired, and the gap is exactly the unmet spending
    assert np.all(out.cons_y[0] <= out.desired_y[0] + 1e-6)
    assert out.desired.sum() - out.funded.sum() == pytest.approx(out.unmet.sum(), rel=1e-9)


def test_constant_wealth_without_returns_flows_or_costs():
    T = 36
    out = _sim(np.zeros((2, T, 2)), _cfg(T, rate=0.0))
    assert np.allclose(out.terminal, 1e6)
    assert np.allclose(out.cost, 0)


def test_higher_costs_never_cheaper():
    rng = np.random.default_rng(2)
    R = rng.normal(0.004, 0.05, (5, 48, 2))
    lo = _sim(R, _cfg(48, trading=ledger.TradingSpec(mode="calendar", cadence_months=1, commission_bps=1)))
    hi = _sim(R, _cfg(48, trading=ledger.TradingSpec(mode="calendar", cadence_months=1, commission_bps=10)))
    zero = _sim(R, _cfg(48, trading=ledger.TradingSpec(mode="calendar", cadence_months=1)))
    assert np.all(hi.cost >= lo.cost - 1e-9)
    assert np.allclose(zero.cost, 0)
    assert np.all(zero.terminal >= hi.terminal - 1e-6)


def test_browne_only_trades_at_annual_reviews():
    T = 36
    R = np.zeros((1, T, 4))
    R[0, 3, 0] = 1.0  # equity doubles in month 3: breach between review dates
    cfg = _cfg(T, A=4, w=(0.25, 0.25, 0.25, 0.25), rate=0.0, trace_path=0,
               trading=ledger.TradingSpec(mode="browne", check_months=12, floor=0.15, ceiling=0.35))
    out = _sim(R, cfg)
    reasons = out.trace["reason"]
    trade_months = [t for t in range(T) if reasons[t] == ledger.RS_BROWNE]
    assert trade_months == [12]  # not at month 4 when the breach happened
    assert np.allclose(out.trace["post"][12], 0.25)
    monthly = _sim(R, _cfg(T, A=4, w=(0.25,) * 4, rate=0.0, trace_path=0,
                           trading=ledger.TradingSpec(mode="browne", check_months=1)))
    assert [t for t in range(T) if monthly.trace["reason"][t] == ledger.RS_BROWNE] == [4]


def test_browne_boundary_equality_does_not_trigger():
    T = 13
    R = np.zeros((1, T, 4))
    # make equity exactly 35% at the review: 0.25*x / (0.75 + 0.25*x) = 0.35 -> x = 1.6153846...
    R[0, 0, 0] = 0.35 * 0.75 / (0.25 * 0.65) - 1
    out = _sim(R, _cfg(T, A=4, w=(0.25,) * 4, rate=0.0, trace_path=0,
                       trading=ledger.TradingSpec(mode="browne", check_months=12)))
    assert out.trace["pre"][12][0] == pytest.approx(0.35)
    assert out.trace["reason"][12] == ledger.RS_NONE


def test_future_return_mutation_does_not_change_past_decisions():
    rng = np.random.default_rng(3)
    T = 48
    R = rng.normal(0.004, 0.03, (2, T, 2))
    dec = np.zeros((2, T), dtype=np.int64)
    dec[:, 24:] = 1
    sched = np.zeros((T, 2, 2))
    sched[:, 0] = [0.7, 0.3]
    sched[:, 1] = [0.3, 0.7]
    kw = dict(sched=sched, trace_path=0, trading=ledger.TradingSpec(mode="absolute_band", abs_band=0.05))
    a = _sim(R, _cfg(T, **kw), dec)
    R2 = R.copy()
    R2[:, 30:] *= -3
    b = _sim(R2, _cfg(T, **kw), dec)
    assert np.allclose(a.trace["trade"][:31], b.trace["trade"][:31])
    assert np.array_equal(a.trace["reason"][:31], b.trace["reason"][:31])


def test_cash_flow_targeting_reduces_rebalancing_turnover_for_contributors():
    rng = np.random.default_rng(4)
    T = 120
    R = rng.normal(0.004, 0.04, (50, T, 2))
    prop = _sim(R, _cfg(T, spend_mode=ledger.SP_SIGNED, q_signed=-0.08))
    cf = _sim(R, _cfg(T, spend_mode=ledger.SP_SIGNED, q_signed=-0.08,
                      trading=ledger.TradingSpec(mode="calendar", cadence_months=12, funding="cash_flow_targeting")))
    assert cf.turnover.mean() < prop.turnover.mean()
    assert np.allclose(cf.contributions, prop.contributions)


def test_withdrawal_funding_orders_balance():
    rng = np.random.default_rng(5)
    T = 60
    R = rng.normal(0.003, 0.03, (10, T, 3))
    for mode in ("proportional", "overweight_first", "cash_first", "bond_ladder_first", "cash_flow_targeting"):
        cfg = _cfg(T, A=3, w=(0.5, 0.3, 0.2), rate=0.05, cash_index=2, defensive=np.array([0, 1.0, 1.0]),
                   trading=ledger.TradingSpec(mode="calendar", cadence_months=12, funding=mode))
        out = _sim(R, cfg)
        assert np.all(out.terminal >= 0)
        assert np.allclose(out.funded + out.unmet, out.desired)


def test_target_weights_validated():
    with pytest.raises(ValueError):
        _sim(np.zeros((1, 12, 2)), _cfg(12, w=(0.6, 0.6)))
    with pytest.raises(ValueError):
        _sim(np.zeros((1, 12, 2)), _cfg(12, trading=ledger.TradingSpec(reserve_years=2)))


def test_bmin_solver_cases():
    bs = [0.0, 0.25, 0.5, 0.75, 1.0]
    assert solve_bmin(np.array([0.95, 0.96, 0.97, 0.9, 0.8]), bs, 0.9)["status"] == "no_bonds_needed"
    r = solve_bmin(np.array([0.7, 0.8, 0.92, 0.95, 0.88]), bs, 0.9)
    assert r["b_min"] == 0.5 and r["bracket"] == [0.25, 0.5] and r["intervals"] == [[0.5, 0.75]]
    d = solve_bmin(np.array([0.7, 0.91, 0.85, 0.93, 0.8]), bs, 0.9)
    assert d["status"] == "disconnected" and d["intervals"] == [[0.25, 0.25], [0.75, 0.75]]
    n = solve_bmin(np.array([0.5, 0.6, 0.6, 0.5, 0.4]), bs, 0.9)
    assert n["b_min"] is None and n["status"] == "no_feasible_allocation"


def test_success_metrics():
    first = np.array([-1, 10, 200, 359, 360])
    assert success(first, 360).mean() == pytest.approx(0.4)  # only -1 (never) and 360 succeed at 30y
    S = np.linspace(1, 0, 500)
    assert until_death_success(np.array([-1, -1]), S) == 1.0
    assert until_death_success(np.array([499, -1]), S) == pytest.approx(1.0)  # dead by then
    lo, hi = wilson(0.5, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)
