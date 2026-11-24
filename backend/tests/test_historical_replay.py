"""Historical replay: point-in-time information, accounting reconciliation, policy behaviour and determinism."""
import numpy as np
import pandas as pd
import pytest

from lifecycle.studies import historical_replay as H


@pytest.fixture(scope="module")
def run():
    spec = H.HistoricalReplaySpec(start="2008-01", end="2013-12", forward_paths=0, experiments=False,
                                  estimation_window_months=60, min_history_months=24,
                                  policies=("sixty_forty", "target_date", "vol_target", "pp_multi_asset", "lifecycle_adaptive"))
    h = H.load_history(spec)
    return spec, h, H.replay(spec, h, list(spec.policies))


def test_information_set_excludes_the_future(run):
    spec, h, res = run
    for t, s in enumerate(res["snaps"]):
        d = h.dates[t]
        assert pd.Timestamp(s["info_last_return"]) < d                       # returns through t-1 only
        if s["info_last_cpi"]:
            assert pd.Timestamp(s["info_last_cpi"]) <= d - pd.offsets.MonthEnd(2)   # CPI lag: through t-2
        assert pd.Timestamp(s["window"][1]) < d


def test_decisions_do_not_change_when_future_returns_change(run):
    spec, h, res = run
    k = 30
    h2 = H.History(**{**h.__dict__})
    h2.R = h.R.copy()
    h2.R.loc[h.dates[k]:] = h2.R.loc[h.dates[k]:] * 3 + 0.05            # rewrite month k onward
    H._SNAPS.clear()
    res2 = H.replay(spec, h2, ["vol_target", "lifecycle_adaptive"])
    for p in ("vol_target", "lifecycle_adaptive"):
        a = np.array(res["policies"][p]["series"]["target"])
        b = np.array(res2["policies"][p]["series"]["target"])
        assert np.allclose(a[:k + 1], b[:k + 1])      # the target for month k is set before month k's return
        assert not np.allclose(a[k + 2:], b[k + 2:])


def test_holdings_and_wealth_reconcile(run):
    spec, h, res = run
    for p, r in res["policies"].items():
        s = r["series"]
        hold = np.array(s["holdings_end"])
        assert np.allclose(hold.sum(axis=1), s["wealth"], rtol=1e-4)
        post = np.array(s["w_post"])
        assert np.allclose(post.sum(axis=1), 1.0, atol=1e-4)
        # month-t return of the post-trade portfolio equals post weights x realised month-t returns
        R = h.R.reindex(h.dates)[res["candidates"]].fillna(0).to_numpy()
        twr = (post * R).sum(axis=1)
        assert np.allclose(twr, s["twr"], atol=2e-4)
        # contributions arrive at the start of the month, 15% of salary / 12, before retirement
        assert np.allclose(s["contrib"], np.array(s["salary"]) * spec.investor.savings_rate / 12, rtol=1e-6)


def test_costs_match_executed_notional(run):
    spec, h, res = run
    rate = (spec.costs.commission_bps + spec.costs.half_spread_bps) / 1e4
    s = res["policies"]["vol_target"]["series"]
    trades = np.abs(np.array(s["trades"])).sum(axis=1)
    assert np.allclose(s["cost"], trades * rate, rtol=2e-3, atol=0.05)


def test_static_keeps_target_glidepath_follows_age_risk_policy_follows_signals(run):
    spec, h, res = run
    tgt = lambda p: np.array(res["policies"][p]["series"]["target"])  # noqa: E731
    c = res["candidates"]
    i_eq = c.index("us_eq")
    s6040 = tgt("sixty_forty")
    assert np.allclose(s6040, s6040[0])                                  # constant strategic target
    pre = np.array(res["policies"]["sixty_forty"]["series"]["w_pre"])
    assert np.abs(pre[:, i_eq] - 0.6).max() > 0.01                       # holdings drift between rebalances
    reasons = res["policies"]["sixty_forty"]["series"]["reason"]
    assert all(r in (0, 1, 3) for r in reasons)                          # only initial / band trades
    td = tgt("target_date")
    eq = td[:, i_eq] + (td[:, c.index("intl_eq")] if "intl_eq" in c else 0)
    ages = np.array(res["policies"]["target_date"]["series"]["salary"]) * 0 + spec.investor.start_age + np.arange(len(eq)) / 12
    assert np.allclose(eq, np.clip((110 - ages) / 100, 0.3, 0.9), atol=1e-9)
    vt = tgt("vol_target")[:, i_eq]
    assert vt.std() > 0.01 and vt.max() <= 0.6 + 1e-9                    # scales down only, responds to risk


def test_lifecycle_target_responds_to_investor_state(run):
    spec, h, res = run
    m = res["snaps"][-1]
    base = {"age": 50.0, "salary": 90_000.0, "years_to_retirement": 15.0, "liability_duration": 20.0, "funding_ratio": 1.0}
    rich = H.lifecycle_target(m, {**base, "wealth": 2e6, "human_capital": 3e5, "pv_liabilities": 1.5e6}, spec)
    poor = H.lifecycle_target(m, {**base, "wealth": 2e5, "human_capital": 3e5, "pv_liabilities": 1.5e6}, spec)
    no_hc = H.lifecycle_target(m, {**base, "wealth": 2e6, "human_capital": 0.0, "pv_liabilities": 1.5e6}, spec)
    a = rich[2]["alpha_total_wealth"]
    if a < 1:
        assert poor[2]["risky_share"] >= rich[2]["risky_share"]           # more human capital relative to wealth -> more risk
        assert no_hc[2]["risky_share"] <= rich[2]["risky_share"]
    assert rich[2]["hedge_ratio"] < poor[2]["hedge_ratio"]                # liabilities large vs wealth -> bigger hedge


def test_forward_vectorised_targets_match_scalar_policy(run):
    spec, h, res = run
    m = res["snaps"][-1]
    st = {"age": 45.0, "salary": 80_000.0, "years_to_retirement": 20.0, "human_capital": 4e5, "pv_liabilities": 1.2e6,
          "liability_duration": 22.0, "funding_ratio": 1.0, "wealth": 3e5}
    W = np.array([1e5, 3e5, 9e5])
    rng = np.random.default_rng(0)
    trend = np.vstack([m["trend"] + rng.normal(0, 0.05, len(m["trend"])) for _ in W])
    vs = np.vstack([m["vol_short"] * (1 + rng.uniform(-0.3, 0.6)) for _ in W])
    for pol in ("lifecycle_adaptive", "crra_parametric", "inverse_vol", "trend_tsmom"):
        vec = H.forward_targets(pol, m, spec, st, W, trend, vs, None, None, {})
        for j in range(len(W)):
            mm = dict(m)
            mm["trend"], mm["vol_short"] = trend[j], vs[j]
            one = H.target(pol, mm, {**st, "wealth": float(W[j])}, spec)["final"]
            assert np.allclose(vec[j], one, atol=1e-6), (pol, j)


def test_replay_is_deterministic(run):
    spec, h, res = run
    again = H.replay(spec, h, ["lifecycle_adaptive"])
    assert again["policies"]["lifecycle_adaptive"]["series"]["wealth"] == res["policies"]["lifecycle_adaptive"]["series"]["wealth"]


def test_unavailable_policy_is_reported_not_proxied():
    spec = H.HistoricalReplaySpec(start="2010-01", end="2011-12", forward_paths=0, experiments=False,
                                  candidates=("us_eq", "ust_10y", "ust_30y", "tbill"), policies=("pp_classic", "sixty_forty"))
    h = H.load_history(spec)
    res = H.replay(spec, h, ["pp_classic", "sixty_forty"])
    assert res["policies"]["pp_classic"]["available"] is False
    assert res["policies"]["sixty_forty"]["available"] is True


def test_forward_starts_from_the_exact_final_state(run):
    spec, h, res = run
    r = res["policies"]["lifecycle_adaptive"]
    hold = np.array(r["series"]["holdings_end"][-1])
    snap = res["snaps"][-1] if res["fixed_set"] is None else H.restrict(res["snaps"][-1], res["fixed_set"])
    spec2 = spec.model_copy(update={"forward_paths": 40})
    f = H.forward(spec2, h, res["candidates"], "lifecycle_adaptive", 1, snap, hold, r["series"]["salary"][-1])
    assert f["available"] and f["start_wealth"] == pytest.approx(r["series"]["wealth"][-1], rel=1e-4)
    assert 0 <= f["p_no_shortfall"] <= 1 and f["months"] > 0


def test_vendor_publication_lag_on_returns_does_not_drop_cash(monkeypatch):
    """Regression: return files with an ingestion lag (WRDS) made T-bills look unknown and crashed the replay."""
    real_wide = H._wide

    def lagged(ids):
        v, a = real_wide(ids)
        return v, a + pd.Timedelta(days=40)
    monkeypatch.setattr(H, "_wide", lagged)
    H._SNAPS.clear()
    spec = H.HistoricalReplaySpec(start="2010-01", end="2011-06", forward_paths=0, experiments=False, min_history_months=24,
                                  estimation_window_months=60, policies=("sixty_forty", "lifecycle_adaptive"))
    h = H.load_history(spec)
    res = H.replay(spec, h, list(spec.policies))
    assert all("tbill" in s["eligible"] for s in res["snaps"])
    assert res["policies"]["lifecycle_adaptive"]["available"]
