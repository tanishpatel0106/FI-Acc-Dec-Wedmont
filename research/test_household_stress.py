"""Independent stress-accounting and monotonicity checks."""
import numpy as np
import pandas as pd
from prepare_household_bridge import stress_path


def frame(cash=0, portfolio=0, earned=1200, other=0, expense=100):
    return pd.DataFrame(dict(cash=[cash],taxable_portfolio=[portfolio],earned_income=[earned],
                             nonlabor_income=[other],expense=[expense]))


def test_later_income_does_not_repair_a_missed_payment():
    result=stress_path(frame(earned=2400),"expense",net_fraction=1,equity_loss=0,bond_loss=0,reserve_months=0)
    assert result["funded"][0]==0
    assert result["unmet"][0]==600
    assert result["terminal"][0]==600


def test_cash_only_excludes_marketable_assets():
    d=frame(portfolio=10000,earned=0)
    full=stress_path(d,"expense")
    cash=stress_path(d,"expense",include_market_assets=False)
    assert full["funded_and_reserve"][0]==1
    assert cash["funded"][0]==0


def test_all_income_stop_weakly_reduces_resources():
    d=frame(cash=900,earned=1200,other=1200)
    baseline=stress_path(d,"expense")
    stressed=stress_path(d,"expense",interrupt_nonlabor=True)
    assert stressed["terminal"][0]<=baseline["terminal"][0]
    assert stressed["unmet"][0]>=baseline["unmet"][0]


def test_initial_loss_applies_only_to_marketable_holdings():
    d=frame(cash=100,portfolio=1000,earned=0,expense=1)
    result=stress_path(d,"expense",interrupt_months=0)
    assert np.isclose(result["terminal"][0],100+.72*1000-12)
