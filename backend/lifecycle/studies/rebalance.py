"""E19-E22 / F4: rebalancing and cash-flow execution laboratory (brief section 7).

The target allocation and the spending rule are held fixed; only the TradingPolicy changes. Every
strategy is evaluated on the same tensor, so differences are paired. Costs are charged on executed
notional (commission + half spread + quadratic slippage). No after-tax claims are made (no tax lots).
"""
from typing import Any

import numpy as np
from pydantic import Field

from lifecycle.data import panel
from lifecycle.engine import fixed_income
from lifecycle.studies import common as S

DEFAULT_STRATEGIES = ("none_buyhold", "calendar_1m", "calendar_3m", "calendar_6m", "calendar_12m",
                      "absolute_band_5pp", "absolute_band_5pp_edge", "relative_band_20pct", "browne_15_35",
                      "browne_15_35_monthly", "cash_flow_targeting", "withdraw_overweight_first", "cash_first_floor",
                      "bond_ladder_first", "volatility_band", "utility_net_of_cost")


class RebalanceSpec(S.Frozen):
    data: S.StudyData = Field(default_factory=lambda: S.StudyData(universe="core_duration"))
    scenario: S.StudyScenario = Field(default_factory=lambda: S.StudyScenario(n_paths=2000))
    investor: S.StudyInvestor = Field(default_factory=lambda: S.StudyInvestor(horizon_years=30))
    preferences: S.StudyPrefs = Field(default_factory=S.StudyPrefs)
    allocation: dict[str, float] = Field(default_factory=lambda: {"us_eq": 0.55, "ust_10y": 0.35, "tbill": 0.10})
    allocation_label: str = "55/35/10 equity / 10Y Treasury / T-bills"
    strategies: tuple[str, ...] = DEFAULT_STRATEGIES
    baseline: str = "calendar_12m"
    withdrawal: float = Field(0.04, ge=0, le=0.15)
    withdrawal_grid: tuple[float, ...] = (0.0, 0.03, 0.05, 0.07)
    cost_grid_bps: tuple[float, ...] = (0.0, 2.0, 5.0, 10.0, 20.0)
    main_cost_bps: float = 5.0
    slippage_bps: float = 1.0
    reserve_grid: tuple[float, ...] = (0.0, 1.0, 2.0, 3.0)
    cadences: tuple[int, ...] = (1, 3, 6, 12)
    bands_pp: tuple[float, ...] = (0.025, 0.05, 0.10)
    contribution_q: float = -0.05
    label: str | None = None


def _costs(bps: float, slip: float) -> S.StudyCosts:
    # split the headline per-side cost into commission (40%) and half spread (60%)
    return S.StudyCosts(commission_bps=0.4 * bps, half_spread_bps=0.6 * bps, slippage_bps=slip)


def run_rebalance(spec: RebalanceSpec, progress: S.Progress) -> dict[str, Any]:
    u = S.universe_or_raise(spec.data)
    progress("generating_scenarios", 0.02)
    es = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences)
    ten = S.get_tensor(es)
    ctx = S.get_context(es, ten, es.scenario.seed)
    assets = ten.assets
    w = S.weights_vector(spec.allocation, assets)
    cov = S.hist_cov(u, assets)
    gamma = spec.preferences.gamma
    uf = spec.preferences.util_floor_annual
    T = ten.n_months
    yrs = T / 12.0
    mh = spec.investor.horizon_years * 12
    main_c = _costs(spec.main_cost_bps, spec.slippage_bps)

    def ev(name, costs=main_c, rate=spec.withdrawal, record=False, trace=-1, spend="fixed_real", q=0.0, **over):
        return S.run(ctx, w, S.strategy(name, costs, **over), rate=rate, record=record, trace=trace, cov=cov,
                     util_floor=uf, spend=spend, q=q)

    outs = {}
    for i, name in enumerate(spec.strategies):
        outs[name] = ev(name, record=True)
        progress("simulating", 0.05 + 0.35 * (i + 1) / len(spec.strategies))
    base = outs[spec.baseline]
    frontier = []
    for name, o in outs.items():
        avgW = np.maximum(o.wealth_y[:, :-1].mean(axis=1), 1.0)
        row = {"strategy": name, "family": S.STRATEGY_FAMILY.get(name, "other"),
               "turnover_one_way_per_year": float(o.turnover.mean() / 2 / yrs),
               "flow_notional_per_year": float(o.flow_notional.mean() / yrs),
               "cost_bps_per_year": float(np.mean(o.cost / avgW) / yrs * 1e4),
               "cost_usd_per_year": float(o.cost.mean() / yrs), "trades_per_year": float(o.n_trades.mean() / yrs),
               "ce": S.ce_of(o, gamma), "success": float(S.success(o.first_shortfall, mh).mean()),
               "median_terminal": float(np.median(o.terminal)), "mdd_median": float(np.median(o.max_drawdown)),
               "first5y_shortfall": float(np.mean((o.first_shortfall >= 0) & (o.first_shortfall < 60))),
               "first10y_shortfall": float(np.mean((o.first_shortfall >= 0) & (o.first_shortfall < 120)))}
        if name != spec.baseline:
            row["delta_ce"] = S.delta_block(o, base, gamma, n_boot=150)
            row["delta_success"] = S.paired_success_diff(S.success(o.first_shortfall, mh),
                                                         S.success(base.first_shortfall, mh))
        frontier.append(row)

    # RB-05 calendar x cost and threshold x cost heatmaps: dCE vs buy-and-hold at the same cost
    progress("cost grid", 0.45)
    heat = {"costs_bps": list(spec.cost_grid_bps), "calendar": {"rows": [], "delta": [], "success": []},
            "bands": {"rows": [], "delta": [], "success": []}}
    for c in spec.cost_grid_bps:
        cc = _costs(c, spec.slippage_bps)
        nb = ev("none_buyhold", costs=cc)
        for cad in spec.cadences:
            o = ev("calendar_12m", costs=cc, cadence_months=cad)
            heat["calendar"].setdefault("_tmp", {}).setdefault(cad, []).append(
                (S.delta_block(o, nb, gamma, n_boot=0)["delta"],
                 float(S.success(o.first_shortfall, mh).mean() - S.success(nb.first_shortfall, mh).mean())))
        for b in spec.bands_pp:
            o = ev("absolute_band_5pp", costs=cc, abs_band=b)
            heat["bands"].setdefault("_tmp", {}).setdefault(b, []).append(
                (S.delta_block(o, nb, gamma, n_boot=0)["delta"],
                 float(S.success(o.first_shortfall, mh).mean() - S.success(nb.first_shortfall, mh).mean())))
    for key, rows, lab in (("calendar", spec.cadences, "every %d months"), ("bands", spec.bands_pp, "%.1fpp band")):
        tmp = heat[key].pop("_tmp")
        for r in rows:
            heat[key]["rows"].append(lab % (r if key == "calendar" else r * 100))
            heat[key]["delta"].append([x[0] for x in tmp[r]])
            heat[key]["success"].append([x[1] for x in tmp[r]])
    heat["units"] = {"x": "per-side cost, bps of traded notional (40%% commission, 60%% half spread) + %.1f bps/$1m "
                          "slippage" % spec.slippage_bps, "z": "paired dCE vs buy-and-hold at the same cost"}

    # RB-06 cash-flow rebalance savings: contributors, zero-flow and withdrawers
    progress("cash-flow savings", 0.55)
    cf = []
    for lab, kw in (("net contributor (q=%.0f%%)" % (spec.contribution_q * 100), {"spend": "signed", "q": spec.contribution_q}),
                    ("zero net flow", {"spend": "signed", "q": 0.0}),
                    ("withdrawer (4%)", {"rate": 0.04}), ("withdrawer (6%)", {"rate": 0.06})):
        a = ev("calendar_12m", **kw)
        b = ev("cash_flow_targeting", **kw)
        saved = (a.turnover - b.turnover) / 2 / yrs
        cf.append({"scenario": lab, "turnover_calendar": float(a.turnover.mean() / 2 / yrs),
                   "turnover_cf_aware": float(b.turnover.mean() / 2 / yrs),
                   "saved_quantiles": np.quantile(saved, [0.05, 0.25, 0.5, 0.75, 0.95]).tolist(),
                   "delta_ce": S.delta_block(b, a, gamma, n_boot=0)["delta"],
                   "cost_saved_usd_per_year": float((a.cost - b.cost).mean() / yrs)})

    # RB-07 utility-net-of-cost decision breakdown
    un = outs.get("utility_net_of_cost")
    no_trade = None
    if un is not None:
        tot = un.accepted + un.rejected
        no_trade = {"accepted_per_path": float(un.accepted.mean()), "rejected_per_path": float(un.rejected.mean()),
                    "accept_rate": float(un.accepted.sum() / max(tot.sum(), 1)),
                    "holdout_delta_vs_calendar_12m": S.delta_block(un, base, gamma, n_boot=150),
                    "holdout_delta_vs_monthly": S.delta_block(un, outs.get("calendar_1m", base), gamma, n_boot=150),
                    "rule": "trade iff 0.5*gamma*d'Sigma d*12*W > estimated cost, Sigma from the calibration window",
                    "error_rate_note": "per-decision error rates are not identified; holdout dCE on disjoint "
                                       "evaluation paths is reported instead"}

    # RB-08 liquidity runway fan for the cash-floor strategy at several reserve sizes
    progress("liquidity", 0.62)
    runway = []
    for ry in spec.reserve_grid:
        if "tbill" not in assets:
            break
        o = ev("cash_first_floor", record=True, reserve_years=float(ry)) if ry > 0 else ev(
            "calendar_12m", record=True, funding="cash_first")
        rw = np.where(o.runway_y >= 0, o.runway_y, np.nan)
        runway.append({"reserve_years": ry, "fan": S.fan(np.nan_to_num(rw, nan=0.0)),
                       "p_shortfall": float(1 - S.success(o.first_shortfall, mh).mean()),
                       "first10y_shortfall": float(np.mean((o.first_shortfall >= 0) & (o.first_shortfall < 120))),
                       "refills_per_year": float(o.n_trades.mean() / yrs), "ce": S.ce_of(o, gamma)})

    # RB-09 event statistics
    events = []
    for name, o in outs.items():
        per = np.where(o.n_trades > 0, o.turnover / np.maximum(o.n_trades, 1) / 2, np.nan)
        events.append({"strategy": name, "trades_per_year_quantiles": np.quantile(o.n_trades / yrs,
                                                                                  [0.05, 0.25, 0.5, 0.75, 0.95]).tolist(),
                       "trade_size_one_way_quantiles": np.nanquantile(per, [0.05, 0.25, 0.5, 0.75, 0.95]).tolist()
                       if np.isfinite(per).any() else None,
                       "trades_by_year_mean": S.to_list(np.diff(np.concatenate([[0], np.cumsum(
                           (o.turnover_y > 0).mean(axis=0))])), 4)})

    # RB-10 cost decomposition and lost-growth drag (CE with costs vs the same strategy at zero cost)
    progress("cost decomposition", 0.7)
    decomp = []
    for name in spec.strategies:
        o = outs[name]
        z = ev(name, costs=S.StudyCosts())
        avgW = np.maximum(o.wealth_y[:, :-1].mean(axis=1), 1.0)
        decomp.append({"strategy": name,
                       "commission_bps_yr": float(np.mean(o.cost_commission / avgW) / yrs * 1e4),
                       "spread_bps_yr": float(np.mean(o.cost_spread / avgW) / yrs * 1e4),
                       "slippage_bps_yr": float(np.mean(o.cost_slippage / avgW) / yrs * 1e4),
                       "ce_drag_vs_zero_cost": S.delta_block(o, z, gamma, n_boot=0)["delta"],
                       "label": "pre-tax; no tax lots modelled"})

    # RB-11 withdrawal funding race
    progress("funding race", 0.78)
    race = {"r": list(spec.withdrawal_grid), "modes": {}}
    for mode in ("proportional", "cash_first", "overweight_first", "bond_ladder_first"):
        rows = []
        for r in spec.withdrawal_grid:
            o = S.run(ctx, w, S.strategy("calendar_12m", main_c, funding=mode), rate=r, cov=cov, util_floor=uf)
            rows.append({"funded_mean": float(o.funded.mean()), "success": float(S.success(o.first_shortfall, mh).mean()),
                         "ce": S.ce_of(o, gamma), "unmet_mean": float(o.unmet.mean())})
        race["modes"][mode] = rows

    # RB-12 ex-ante risk-budget drift (weights at the start of each year, covariance from the calibration window)
    progress("risk budget", 0.85)
    risk = {}
    try:
        _, cm, cz = _curve()
    except Exception:
        cm = cz = None
    dur = np.array([_duration(a, cm, cz) for a in assets])
    tgt_vol = float(np.sqrt(w @ cov @ w * 12))
    for name in ("none_buyhold", "calendar_12m", "absolute_band_5pp", "volatility_band"):
        if name not in outs:
            continue
        W_ = outs[name].weights_y
        vol = np.sqrt(np.einsum("nya,ab,nyb->ny", W_, cov, W_) * 12)
        risk[name] = {"vol_fan": S.fan(vol), "duration_contribution_mean": S.to_list((W_ * dur).mean(axis=0), 4),
                      "corr_eq_bond_window": float(np.corrcoef(u.real["us_eq"], u.real["ust_10y"])[0, 1])
                      if "ust_10y" in assets else None}
    risk_meta = {"target_vol": tgt_vol, "durations": dict(zip(assets, dur.tolist())),
                 "estimation": "Sigma estimated on the calibration window only (%s..%s); applied ex ante" % (
                     u.start.date(), u.end.date()), "validation": _lagged_validation(u, w)}
    return {"kind": "rebalance", "universe": S.universe_block(u), "scenario": S.scenario_block(ten),
            "n_paths": ten.n_paths, "allocation": dict(zip(assets, w.tolist())), "allocation_label": spec.allocation_label,
            "withdrawal": spec.withdrawal, "baseline": spec.baseline, "main_cost_bps": spec.main_cost_bps,
            "frontier": frontier, "heatmaps": heat, "cash_flow_savings": cf, "no_trade": no_trade, "runway": runway,
            "events": events, "cost_decomposition": decomp, "funding_race": race, "risk_drift": risk,
            "risk_meta": risk_meta, "warnings": S.common_warnings(u, ten), "timings": {},
            "summary": {"universe": u.name, "n_strategies": len(outs), "baseline": spec.baseline}}


def _curve():
    ids = ["gsw_nom_%02d" % m for m in range(1, 31)]
    w = panel.wide(ids).dropna()
    row = w.iloc[-1]
    return w.index[-1].date().isoformat(), np.array([int(c[-2:]) for c in row.index], float), row.to_numpy()


def _duration(a: str, cm, cz) -> float:
    if a.startswith("ust_"):
        m = float(a.split("_")[1][:-1])
        y = float(np.interp(m, cm, cz)) if cm is not None else 0.04
        return fixed_income.modified_duration(y, y, m)
    if a == "tips":
        return 7.0
    if a == "tbill":
        return 1.0 / 12.0
    return 0.0


def _lagged_validation(u, w) -> dict[str, Any]:
    """Out-of-sample check of the ex-ante vol estimate: trailing 60m covariance vs realised next-12m vol."""
    R = u.real.to_numpy() @ w
    X = u.real.to_numpy()
    pred, real = [], []
    for t in range(60, len(R) - 12, 12):
        c = np.cov(X[t - 60:t], rowvar=False)
        pred.append(float(np.sqrt(w @ c @ w * 12)))
        real.append(float(R[t:t + 12].std() * np.sqrt(12)))
    if not pred:
        return {"available": False}
    p, r = np.array(pred), np.array(real)
    return {"available": True, "n": len(p), "mean_predicted": float(p.mean()), "mean_realised": float(r.mean()),
            "corr": float(np.corrcoef(p, r)[0, 1]), "mae": float(np.abs(p - r).mean()),
            "method": "trailing-60m covariance at each year start vs realised vol over the next 12 months"}


def trace_strategy(spec: RebalanceSpec, strategy: str, path: int) -> dict[str, Any]:
    from lifecycle.studies.frontier import trace_payload

    es = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences)
    ten = S.get_tensor(es)
    ctx = S.get_context(es, ten, es.scenario.seed)
    u = S.universe_or_raise(spec.data)
    w = S.weights_vector(spec.allocation, ten.assets)
    o = S.run(ctx, w, S.strategy(strategy, _costs(spec.main_cost_bps, spec.slippage_bps)), rate=spec.withdrawal,
              record=True, trace=path, cov=S.hist_cov(u, ten.assets), util_floor=spec.preferences.util_floor_annual)
    p = trace_payload(o, ctx, ten.assets, path)
    # sources & uses reconciliation (RB-04)
    m = p["monthly"]
    tr = np.array(m["trades"])
    sales = float(-tr[tr < 0].sum())
    buys = float(tr[tr > 0].sum())
    w0 = float(ctx.investor.initial_wealth)
    wend = float(o.terminal[path])
    draws = float(np.sum(m["funded_draw"]))
    contrib = float(np.sum(m["contribution"]))
    cost = float(np.sum(m["cost"]))
    Rj = ten.real_returns[path]
    post = np.array(m["post_weights"])
    wpt = np.array(m["wealth_post_trade"])
    market = float(np.sum(wpt * np.sum(post * Rj, axis=1)))  # independent P&L from post-trade holdings x R
    p["sources_uses"] = {"start_wealth": w0, "end_wealth": wend, "funded_spending": draws, "contributions": contrib,
                         "other_income": float(np.sum(m["other_income"])), "asset_sales": sales, "asset_purchases": buys,
                         "trading_cost": cost, "market_return_and_income": market,
                         "reconciliation_residual": wend - (w0 - draws + contrib - cost + market),
                         "identity": "W_end = W_0 - funded draws + contributions - trading costs + market P&L "
                                     "(coupons/dividends are inside total returns)"}
    p["strategy"] = strategy
    return p
