"""Multi-asset lifecycle simulation from a dated start: no hindsight, multi-asset and age-varying allocations."""
import numpy as np
import pandas as pd

from lifecycle.studies import historical_replay as H
from lifecycle.studies import lifecycle_sim as LS


def test_simulated_from_start_uses_only_prior_information_and_varies_with_age():
    r = LS.run_lifecycle_sim(LS.LifecycleSimSpec(start="2012-01", n_paths=60, min_history_months=24, estimation_window_months=60,
                                                 policies=("pp_lifecycle", "sixty_forty")), lambda s, p: None)
    assert pd.Timestamp(r["information_until"]) < pd.Timestamp("2012-01-01")
    f = r["policies"]["pp_lifecycle"]["forward"]
    assert f["available"] and f["start_wealth"] > 0
    growth = [c for c in f["forward_universe"] if r["block_of"][c] == "growth"]
    g = [sum(a["mean"][c] for c in growth) for a in f["allocation_by_age"]]
    assert g[0] > g[-1] + 0.2                       # growth share falls as human capital is consumed
    held = [c for c, w in f["allocation_by_age"][0]["mean"].items() if w > 0.02]
    assert len(held) >= 3                                                    # growth + duration + cash at least
    assert len(held) >= 4 or r["excluded_short_history"]                    # fewer only when sleeves lack history (reported)
    s = r["policies"]["sixty_forty"]["forward"]["allocation_by_age"]
    assert abs(s[0]["mean"]["us_eq"] - 0.6) < 0.05


def test_history_then_simulated_continues_from_the_realised_state():
    r = LS.run_lifecycle_sim(LS.LifecycleSimSpec(start="2011-01", scenario_source="history_then_simulated", n_paths=50,
                                                 min_history_months=24, estimation_window_months=60, policies=("pp_lifecycle",)),
                             lambda s, p: None)
    v = r["policies"]["pp_lifecycle"]
    assert v["available"] and v["forward"]["start_wealth"] > 0
    assert abs(v["forward"]["start_age"] - v["history"]["ages"][-1]) < 0.1


def test_pp_lifecycle_converges_to_classic_split():
    spec = H.HistoricalReplaySpec(start="2010-01", end="2010-12", forward_paths=0, experiments=False, min_history_months=24,
                                  estimation_window_months=60)
    m = H.market_snapshots(spec, H.load_history(spec))[-1]
    st = {"age": 70.0, "salary": 0.0, "years_to_retirement": 0.0, "liability_duration": 9.0, "funding_ratio": 1.0,
          "wealth": 1e6, "human_capital": 0.0, "pv_liabilities": 5e5}
    w, notes = H.pp_lifecycle_target(m, st, spec)
    assert abs(notes["growth_share"] - 0.25) < 1e-9 and abs(w.sum() - 1) < 1e-9 and np.all(w >= 0)
