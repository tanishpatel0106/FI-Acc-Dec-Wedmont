"""Property tests: wealth never negative, weights on the simplex, floor respected unless flagged."""
import numpy as np
from helpers import run
from hypothesis import given, settings
from hypothesis import strategies as st


@settings(max_examples=40, deadline=None)
@given(seed=st.integers(0, 10_000), share=st.floats(0, 1), rate=st.floats(0, 0.15), vol=st.floats(0.0, 0.12),
       rebalance=st.sampled_from([1, 3, 12]), kappa=st.floats(0, 0.01))
def test_invariants(seed, share, rate, vol, rebalance, kappa):
    rng = np.random.default_rng(seed)
    R = np.maximum(rng.normal(0.003, vol, (60, 240, 2)), -0.9)
    c_min = 200.0
    pension = np.full((60, 240), 100.0)
    out = run(R, [share, 1 - share], w0=500_000.0, rate=rate, pension=pension, rebalance=rebalance, kappa=kappa,
              gamma=3.0, c_min=c_min)
    assert np.all(out.wealth_y >= 0)
    sums = out.weights_y.sum(axis=2)
    assert np.allclose(sums, 1.0, atol=1e-9)
    assert np.all(out.weights_y >= -1e-12)
    floor_breach = out.cons_y < 12 * c_min - 1e-6
    assert not floor_breach.any()
    # paths that could not fund the floor carry the infeasibility flag and a positive shortfall variable
    assert np.all((out.infeasible == 0) | (out.shortfall_var > 0))
