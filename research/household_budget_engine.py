"""Household outlay funding through the existing holdings ledger, without double-counted income."""
import numpy as np

from lifecycle.engine.lifecycle import ledger as L


def run_budget(returns, weights, initial_assets, monthly_outlays, annual_earned, annual_other,
               net_fraction=.85, interrupt_months=0, initial_losses=None, half_spread_bps=5):
    """Income first pays outlays; only the net surplus/deficit crosses the portfolio boundary.

    Income and outlays remain constant in real terms except the stated interruption. This is
    a frozen-state budget scenario, not a forecast of earnings, retirement or household behavior.
    Ledger utility is deliberately unused: recurring outlays include debt principal payments.
    """
    returns = np.asarray(returns,dtype=float)
    n, months, assets = returns.shape
    weights = np.asarray(weights,dtype=float)
    if np.any(weights<0) or not np.isclose(weights.sum(),1):
        raise ValueError("Invalid allocation weights")
    if min(initial_assets,monthly_outlays,annual_earned,annual_other)<0:
        raise ValueError("Budget inputs must be nonnegative")
    losses=np.zeros(assets) if initial_losses is None else np.asarray(initial_losses,dtype=float)
    if np.any(losses<0) or np.any(losses>1):
        raise ValueError("Invalid initial market shock")
    holdings=np.broadcast_to(initial_assets*weights*(1-losses),(n,assets)).copy()
    first=np.full(n,-1,dtype=int)
    unmet=np.zeros(n);funded_gap=np.zeros(n);funded_outlays=np.zeros(n);contributions=np.zeros(n);cost=np.zeros(n)
    bounds=sorted(set([0,min(max(int(interrupt_months),0),months),months]))
    for start,end in zip(bounds,bounds[1:]):
        length=end-start
        income=net_fraction*(annual_other+(0 if start<interrupt_months else annual_earned))/12
        gap=monthly_outlays-income
        config=L.LedgerConfig(w0=initial_assets,retire_m=0,spend_mode=L.SP_SIGNED,rate=0,savings_rate=0,
            sched=L.constant_schedule(weights,length),trading=L.TradingSpec(cadence_months=12,
            funding="proportional",half_spread_bps=half_spread_bps),disc=np.ones(length),beq=np.zeros(length),
            w_ref=max(initial_assets,1.),q_signed=12*gap/max(initial_assets,1.),cash_index=1,
            record_years=False,h0=holdings,t0=start)
        out=L.simulate(returns[:,start:end],np.zeros((n,length),dtype=np.int64),
                       np.zeros((n,length)),np.zeros((n,length)),config)
        holdings=out.holdings_end
        first=np.where((first<0)&(out.first_shortfall>=0),out.first_shortfall+start,first)
        unmet+=out.unmet;funded_gap+=out.funded;contributions+=out.contributions;cost+=out.cost
        funded_outlays+=min(income,monthly_outlays)*length+out.funded
    desired=monthly_outlays*months
    assert np.allclose(funded_outlays+unmet,desired,rtol=1e-10,atol=1e-5)
    assert np.all(holdings>=-1e-8)
    return dict(terminal=holdings.sum(axis=1),unmet=unmet,first_shortfall=first,
        funded_outlays=funded_outlays,desired_outlays=desired,portfolio_funded_gap=funded_gap,
        contributions=contributions,cost=cost,initial_after_shock=float((initial_assets*weights*(1-losses)).sum()))
