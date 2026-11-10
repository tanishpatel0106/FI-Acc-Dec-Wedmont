"""The historical replay calls the canonical Numba ledger one month at a time. These tests prove that doing so
reproduces a whole-horizon run exactly (same holdings, wealth, costs, trades and spending), so sequential,
state-dependent decisions change *only* the targets, never the accounting."""
import numpy as np
import pytest

from lifecycle.engine.lifecycle import ledger as L


def _cfg(sched, T, **kw):
    tr = L.TradingSpec(mode=kw.pop("mode", "calendar"), cadence_months=kw.pop("cadence", 3), abs_band=0.05,
                       check_months=1, commission_bps=1.0, half_spread_bps=2.0, slippage_bps=0.0)
    return L.LedgerConfig(w0=10_000.0, retire_m=kw.pop("retire_m", 200), spend_mode=L.SPEND_MODES["fixed_real"],
                          rate=0.04, savings_rate=0.15, sched=sched, trading=tr, disc=np.ones(T), beq=np.zeros(T),
                          record_years=False, trace_path=0, cash_index=2, **kw)


@pytest.mark.parametrize("mode", ["calendar", "absolute_band"])
def test_sequential_one_month_calls_equal_one_whole_run(mode):
    rng = np.random.default_rng(5)
    T, A = 240, 3
    R = rng.normal([0.007, 0.003, 0.002], [0.045, 0.02, 0.002], (1, T, A))
    labor = np.full((1, T), 4000.0)
    pension = np.zeros((1, T))
    w = np.array([0.6, 0.3, 0.1])
    sched = L.constant_schedule(w, T)
    dec = np.zeros((1, T), dtype=np.int64)
    whole = L.simulate(R, dec, labor, pension, _cfg(sched, T, mode=mode))

    h = None
    spend = 0.0
    walk = []
    costs = 0.0
    for t in range(T):
        out = L.simulate(R[:, t:t + 1], dec[:, t:t + 1], labor[:, t:t + 1], pension[:, t:t + 1],
                         _cfg(sched[t:t + 1], 1, mode=mode, h0=h, t0=t, spend0=spend))
        h, spend = out.holdings_end, float(out.spend_end[0])
        walk.append(out.trace["wealth"][0])
        costs += float(out.cost[0])
    assert np.allclose(h[0], whole.holdings_end[0], rtol=1e-12, atol=1e-8)
    assert np.allclose(walk, whole.trace["wealth"], rtol=1e-12)
    assert costs == pytest.approx(float(whole.cost[0]), rel=1e-10)
    assert whole.terminal[0] == pytest.approx(h[0].sum(), rel=1e-12)


def test_sequential_carries_spending_into_retirement():
    rng = np.random.default_rng(9)
    T, A = 36, 3
    R = rng.normal(0.003, 0.02, (1, T, A))
    labor = np.full((1, T), 3000.0)
    pension = np.zeros((1, T))
    sched = L.constant_schedule(np.array([0.5, 0.3, 0.2]), T)
    dec = np.zeros((1, T), dtype=np.int64)
    whole = L.simulate(R, dec, labor, pension, _cfg(sched, T, retire_m=12))
    h, spend = None, 0.0
    for t in range(T):
        out = L.simulate(R[:, t:t + 1], dec[:, t:t + 1], labor[:, t:t + 1], pension[:, t:t + 1],
                         _cfg(sched[t:t + 1], 1, retire_m=12, h0=h, t0=t, spend0=spend))
        h, spend = out.holdings_end, float(out.spend_end[0])
    assert spend == pytest.approx(float(whole.spend_end[0]))
    assert h[0].sum() == pytest.approx(whole.terminal[0], rel=1e-12)


def test_defaults_unchanged_for_whole_horizon_runs():
    rng = np.random.default_rng(1)
    T = 60
    R = rng.normal(0.004, 0.03, (50, T, 3))
    cfg = _cfg(L.constant_schedule(np.array([0.6, 0.3, 0.1]), T), T)
    cfg.trace_path = -1
    a = L.simulate(R, np.zeros((50, T), dtype=np.int64), np.full((50, T), 4000.0), np.zeros((50, T)), cfg)
    assert a.holdings_end.shape == (50, 3) and np.allclose(a.holdings_end.sum(axis=1), a.terminal)
