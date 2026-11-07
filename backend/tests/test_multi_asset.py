"""Multi-asset allocation: currency returns, point-in-time signals, per-path schedules, and the study contract."""
import numpy as np
import pandas as pd
import pytest

from lifecycle.data.ingest_fx import fx_returns
from lifecycle.studies import common as S
from lifecycle.studies import multi_asset as M


def test_fx_deposit_return_uses_lagged_rate_and_skips_gaps():
    idx = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31", "2020-05-31"])
    spot = pd.Series([1.00, 1.10, 1.10, 1.21], index=idx)
    rate = pd.Series([0.12, 0.24, 0.0, 0.0], index=idx)
    r = fx_returns(spot, rate)
    assert r.index.tolist() == list(idx[1:3])                       # May is not consecutive with March: no bridge
    assert r.iloc[0] == pytest.approx(1.10 * (1 + 0.12 / 12) - 1)    # January's rate accrues over February
    assert r.iloc[1] == pytest.approx(1.0 * (1 + 0.24 / 12) - 1)


def test_trailing_signal_is_point_in_time():
    rng = np.random.default_rng(0)
    R = rng.normal(0, 0.02, (3, 30, 2))
    prefix = rng.normal(0, 0.02, (12, 2))
    cum, vol = M.trailing(R, prefix, 12)
    # the signal at month t never uses month t's own return
    R2 = R.copy()
    R2[:, 20, :] += 0.5
    cum2, _ = M.trailing(R2, prefix, 12)
    assert np.allclose(cum[:, :21], cum2[:, :21])
    assert not np.allclose(cum[:, 21], cum2[:, 21])
    expect = np.prod(1 + R[0, 8:20, 0]) - 1
    assert cum[0, 20, 0] == pytest.approx(expect)
    assert vol.shape == R.shape and np.all(vol >= 0)


def test_erc_equalises_risk_contributions():
    cov = np.array([[0.04, 0.01, 0.0], [0.01, 0.01, 0.0], [0.0, 0.0, 0.0025]])
    w = M.erc(cov)
    rc = w * (cov @ w)
    assert np.allclose(rc, rc.mean(), rtol=1e-3) and w.sum() == pytest.approx(1.0)


def test_per_path_schedule_shapes():
    W = np.random.default_rng(1).random((4, 6, 3))
    sched, state = M.per_path(W)
    assert sched.shape == (6, 4, 3) and state.shape == (4, 6)
    assert np.allclose(sched.sum(axis=2), 1.0) and (state[:, 0] == np.arange(4)).all()


def test_simplex_grid():
    g = M.simplex(["a", "b", "c"], 0.25)
    assert len(g) == 15 and all(abs(sum(x.values()) - 1) < 1e-9 for x in g)


def test_study_runs_on_public_tier_and_full_tier_needs_wrds():
    spec = M.MultiAssetSpec(scenario={"generator": "markov_switching", "n_paths": 200, "n_train_paths": 150},
                            robustness_generators=())
    try:
        r = M.run_multi_asset(spec, lambda s, p: None)
    except S.IncompatibleUniverse:
        pytest.skip("multi-asset public tier not in the synthetic fixture panel")
    names = {row["policy"] for row in r["scorecard"]}
    assert "sixty_forty" in names and len(names) >= 8
    for row in r["scorecard"]:
        assert 0 <= row["success"] <= 1
        if row["policy"] != r["benchmark"]:
            assert row["delta_ce"]["lo"] <= row["delta_ce"]["delta"] <= row["delta_ce"]["hi"]
    for n, w in r["static_weights"].items():
        assert abs(sum(w.values()) - 1) < 1e-3 and min(w.values()) >= 0, n   # reported to 4 decimals
    from lifecycle.data import panel
    if panel.synthetic_mode():   # fixtures carry every sleeve: the full tier must contain the WRDS-only classes
        assert {"gold", "commodities", "hy_credit", "fx_basket"} <= set(panel.universe_data("multi_asset_full").assets)
    else:                        # public data only: the full tier must refuse rather than proxy missing sleeves
        with pytest.raises(S.IncompatibleUniverse):
            M.run_multi_asset(M.MultiAssetSpec(data={"universe": "multi_asset_full"}), lambda s, p: None)
