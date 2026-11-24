"""Budget accounting checks independent of the new empirical estimates."""
import numpy as np

from household_budget_engine import run_budget


def test_income_is_not_double_counted_as_consumption_and_contributions():
    returns=np.zeros((3,12,3))
    result=run_budget(returns,np.array([.6,0,.4]),10000,1000,12000,0,
                      net_fraction=1,half_spread_bps=0)
    assert np.allclose(result['terminal'],10000)
    assert np.allclose(result['funded_outlays'],12000)
    assert np.allclose(result['portfolio_funded_gap'],0)
    assert np.allclose(result['contributions'],0)


def test_later_income_cannot_repair_an_earlier_unmet_outlay():
    result=run_budget(np.zeros((2,12,3)),np.array([0,1,0]),500,1000,24000,0,
                      net_fraction=1,interrupt_months=6,half_spread_bps=0)
    assert np.allclose(result['unmet'],5500)
    assert np.allclose(result['funded_outlays'],6500)
    assert np.allclose(result['terminal'],6000)
    assert (result['first_shortfall']==0).all()


def test_initial_market_losses_reduce_only_exposed_holdings():
    result=run_budget(np.zeros((2,12,3)),np.array([.6,0,.4]),10000,0,0,0,
                      net_fraction=1,initial_losses=np.array([.4,0,.1]),half_spread_bps=0)
    assert np.allclose(result['terminal'],7200)
    assert result['initial_after_shock']==7200


def test_budget_adapter_matches_an_independent_monthly_holdings_loop():
    rng=np.random.default_rng(9)
    returns=rng.uniform(-.04,.04,(4,18,3))
    weights=np.array([.5,.2,.3])
    actual=run_budget(returns,weights,15000,1200,18000,2000,net_fraction=.85,
                      interrupt_months=6,half_spread_bps=0)
    terminal=[];unmet=[]
    for path in returns:
        h=15000*weights.copy();missing=0
        for month,r in enumerate(path):
            income=.85*(2000+(0 if month<6 else 18000))/12
            flow=income-1200
            if flow>=0:
                h+=weights*flow
            else:
                need=-flow;funded=min(need,h.sum());missing+=need-funded
                if h.sum()>0:
                    h*=1-funded/h.sum()
            if month%12==0:
                h=h.sum()*weights
            h*=1+r
        terminal.append(h.sum());unmet.append(missing)
    assert np.allclose(actual['terminal'],terminal,atol=1e-8)
    assert np.allclose(actual['unmet'],unmet,atol=1e-8)
