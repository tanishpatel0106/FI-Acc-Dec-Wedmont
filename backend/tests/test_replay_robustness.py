"""Every policy must return finite, long-only, fully-invested targets for any market state and investor state
(regression: tbill missing, 0.0 ** -0.5 in the CRRA tilt). Scalar and vectorised forms are both exercised."""
import itertools

import numpy as np
import pytest

from lifecycle.studies import historical_replay as H


@pytest.fixture(scope="module")
def snaps():
    spec = H.HistoricalReplaySpec(start="2009-01", end="2010-12", forward_paths=0, experiments=False,
                                  min_history_months=24, estimation_window_months=60)
    h = H.load_history(spec)
    return spec, H.market_snapshots(spec, h)


def _perturb(m, kind):
    mm = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in m.items() if not str(k).startswith("_lc")}
    n = len(mm["eligible"])
    if kind == "zero_vol_short":
        mm["vol_short"] = np.zeros(n)
    elif kind == "huge_vol_short":
        mm["vol_short"] = mm["vol_short"] * 50
    elif kind == "negative_mu":
        mm["mu_ex"] = -np.abs(mm["mu_ex"]) - 0.2
    elif kind == "extreme_mu":
        mm["mu_ex"] = np.linspace(-1, 1, n)
    elif kind == "singular_cov":
        mm["cov"] = np.full((n, n), 0.04) + 1e-12 * np.eye(n)
        mm["vol"] = np.sqrt(np.diag(mm["cov"]))
    elif kind == "zero_trend":
        mm["trend"] = np.zeros(n)
    return mm


STATES = [dict(wealth=0.0, human_capital=0.0, pv_liabilities=0.0), dict(wealth=1.0, human_capital=1e6, pv_liabilities=1e7),
          dict(wealth=5e6, human_capital=0.0, pv_liabilities=1e5)]


def _ok(w):
    assert np.all(np.isfinite(w)) and np.all(w >= -1e-9) and abs(w.sum() - 1) < 1e-6


@pytest.mark.parametrize("kind", ["none", "zero_vol_short", "huge_vol_short", "negative_mu", "extreme_mu", "singular_cov", "zero_trend"])
def test_every_policy_is_robust(snaps, kind):
    spec, ss = snaps
    for m, pol, st in itertools.product(ss[::6], list(H.POLICIES), STATES):
        mm = _perturb(m, kind)
        full = {"age": 45.0, "salary": 50_000.0, "years_to_retirement": 20.0, "liability_duration": 18.0, "funding_ratio": 1.0, **st}
        tg = H.target(pol, mm, full, spec)
        if tg is None:
            continue
        _ok(tg["final"])
        W = np.array([0.0, 1.0, 1e7])
        n = len(mm["eligible"])
        out = H.forward_targets(pol, mm, spec, full, W, np.zeros((3, n)), np.zeros((3, n)) if kind == "zero_vol_short" else np.tile(mm["vol_short"], (3, 1)),
                                np.zeros(3), np.array([0.0, 0.5, 1.0]), {})
        for row in out:
            _ok(row)


def test_minimal_universe_cash_plus_one(snaps):
    spec, ss = snaps
    m = H.restrict(ss[-1], ["us_eq", "tbill"])
    st = {"age": 30.0, "salary": 1.0, "years_to_retirement": 35.0, "liability_duration": 30.0, "funding_ratio": 1.0,
          "wealth": 10.0, "human_capital": 0.0, "pv_liabilities": 0.0}
    for pol in H.POLICIES:
        tg = H.target(pol, m, st, spec)
        if tg is not None:
            _ok(tg["final"])
