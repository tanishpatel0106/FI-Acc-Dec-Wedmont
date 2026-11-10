"""v2 holdings-ledger path engine (brief sections 2.1-2.2, 7).

Unlike the legacy target-weight kernel, every path keeps dollar holdings per asset, so:

* desired, funded and unmet spending are separate quantities (a gap is never free consumption);
* withdrawals and contributions are executed as trades with an explicit funding order;
* rebalancing trades are decided by a TradingPolicy (calendar, bands, Browne 15/35 with an annual
  review, cash-flow targeting, risk band, utility-net-of-cost) and cost is charged on the *executed*
  notional (commission + half spread + quadratic slippage);
* target weights are selected with a decision-time regime signal supplied by the caller (lagged /
  filtered; never the contemporaneous latent state unless the caller explicitly asks for the oracle).

Timing contract per month t:
  known state -> planned flows (contribution / desired draw) -> fund flows by the funding order ->
  trading decision on post-flow weights -> trades + costs -> earn R_{t+1} -> update wealth.
"""
from dataclasses import dataclass, field

import numpy as np
from numba import njit, prange
from numpy.typing import NDArray

# spending modes
SP_FIXED_REAL = 0
SP_FIXED_PCT = 1
SP_GUARDRAILS = 2
SP_AMORTIZED = 3
SP_SIGNED = 4          # planned signed net draw q * W_ref per year (negative = contribution), all months

SPEND_MODES = {"fixed_real": SP_FIXED_REAL, "fixed_pct": SP_FIXED_PCT, "guardrails": SP_GUARDRAILS,
               "amortized": SP_AMORTIZED, "utility_optimal": SP_AMORTIZED, "signed": SP_SIGNED}

# trading triggers
TR_NONE = 0            # buy at targets once, then drift
TR_CALENDAR = 1        # reset to target every `cadence` months
TR_ABS_BAND = 2        # any |w - w*| > band (absolute percentage points)
TR_REL_BAND = 3        # any |w - w*| > band * w*
TR_BROWNE = 4          # at each review (every check_months) any sleeve outside [floor, ceiling] -> reset all
TR_RISK_BAND = 5       # ex-ante vol deviates from target vol by more than risk_thr (relative)
TR_UTILITY = 6         # trade only if projected tracking-error utility loss over review window > cost

TRADE_MODES = {"none_buyhold": TR_NONE, "calendar": TR_CALENDAR, "absolute_band": TR_ABS_BAND,
               "relative_band": TR_REL_BAND, "browne": TR_BROWNE, "risk_band": TR_RISK_BAND,
               "utility_net_of_cost": TR_UTILITY}

# funding order for withdrawals / contributions
CF_PROPORTIONAL = 0
CF_TARGETING = 1       # contributions buy underweights first, withdrawals sell overweights first
CF_OVERWEIGHT = 2      # withdrawals sell overweights first, contributions at target weights
CF_CASH_FIRST = 3      # withdrawals from the cash sleeve first
CF_BOND_FIRST = 4      # withdrawals from defensive (ladder) sleeves first

FUNDING_MODES = {"proportional": CF_PROPORTIONAL, "cash_flow_targeting": CF_TARGETING,
                 "overweight_first": CF_OVERWEIGHT, "cash_first": CF_CASH_FIRST, "bond_ladder_first": CF_BOND_FIRST}

# reason codes in the trace
RS_NONE = 0
RS_INITIAL = 1
RS_CALENDAR = 2
RS_BAND = 3
RS_BROWNE = 4
RS_RISK = 5
RS_UTILITY = 6
RS_REJECTED = 7
REASONS = ["none", "initial", "calendar", "band breach", "Browne 15/35 review breach", "risk band",
           "utility gain > cost", "trade rejected (cost > gain)"]

# integer parameter slots
I_RETIRE, I_SPEND, I_TRADE, I_CADENCE, I_CHECK, I_CF, I_CASH, I_EDGE, I_REC, I_TRACE, I_K, I_T0 = range(12)
N_IP = 12   # I_T0: global month offset of local month 0 (sequential execution; 0 for whole-horizon runs)
# float parameter slots
(F_W0, F_RATE, F_SAVE, F_GUP, F_GLO, F_GSTEP, F_ABS, F_REL, F_FLOOR, F_CEIL, F_COMM, F_SPREAD, F_SLIP,
 F_SLIPSCALE, F_RESERVE, F_GAMMA, F_ETA, F_KSHIFT, F_SCALE, F_UFLOOR, F_WREF, F_Q, F_RISK, F_REVIEW, F_SPEND0) = range(25)
N_FP = 25   # F_SPEND0: annual spending level carried in from a previous sequential call (0 = not yet set)


@njit(cache=True)
def _crra(c, gamma):
    if gamma == 1.0:
        return np.log(c)
    return c ** (1.0 - gamma) / (1.0 - gamma)


@njit(cache=True)
def _trade_cost(dollars, comm, spread, slip, slip_scale):
    a = abs(dollars)
    return a * (comm + spread) + slip * a * a / slip_scale


@njit(cache=True)
def _path(j, R, dec_regime, labor, pension, wtgt_sched, defensive, cov, amort, ip, fp, disc, beq, h0, h_out, s_out,
          o_u, o_first, o_unmet, o_desired, o_funded, o_term, o_mdd, o_turn, o_ntr, o_cost, o_costc, o_costs,
          o_costl, o_flowturn, o_acc, o_rej, o_contrib,
          y_w, y_c, y_un, y_des, y_run, y_wts, y_turn,
          t_pre, t_post, t_tgt, t_trade, t_cost, t_flow, t_reason, t_wealth):
    T = R.shape[1]
    A = R.shape[2]
    K = wtgt_sched.shape[1]
    retire_m = ip[I_RETIRE]
    spend_mode = ip[I_SPEND]
    trade_mode = ip[I_TRADE]
    cadence = max(ip[I_CADENCE], 1)
    check = max(ip[I_CHECK], 1)
    cf_mode = ip[I_CF]
    cash = ip[I_CASH]
    to_edge = ip[I_EDGE]
    rec = ip[I_REC]
    trace = ip[I_TRACE] == j
    comm = fp[F_COMM]
    spr = fp[F_SPREAD]
    slip = fp[F_SLIP]
    slsc = max(fp[F_SLIPSCALE], 1.0)
    gamma = fp[F_GAMMA]
    scale = fp[F_SCALE]
    ufloor = fp[F_UFLOOR]
    n_years = y_c.shape[1]

    h = np.zeros(A)
    tgt = np.zeros(A)
    w = np.zeros(A)
    tr = np.zeros(A)
    sell = np.zeros(A)
    W = fp[F_W0]
    spend = fp[F_SPEND0]
    t0 = ip[I_T0]
    first = -1
    unmet_tot = 0.0
    des_tot = 0.0
    fund_tot = 0.0
    contrib_tot = 0.0
    turn = 0.0
    ntr = 0
    cost_tot = 0.0
    cost_c = 0.0
    cost_s = 0.0
    cost_l = 0.0
    flow_turn = 0.0
    acc = 0
    rej = 0
    util = 0.0
    idx = 1.0
    peak = 1.0
    mdd = 0.0
    started = False
    for t in range(T):
        g = t + t0          # global month: retirement, calendar and review timing use it; arrays use t
        yr = t // 12
        y = labor[j, t]
        p = pension[j, t]
        k = dec_regime[j, t]
        if k < 0:
            k = 0
        if k >= K:
            k = K - 1
        for a in range(A):
            tgt[a] = wtgt_sched[t, k, a]
        if not started:
            h0s = 0.0
            for a in range(A):
                h0s += h0[j, a]
            for a in range(A):
                h[a] = h0[j, a] if h0s > 0.0 else tgt[a] * W
            started = True
            if trace and h0s == 0.0:
                t_reason[t] = RS_INITIAL
        W = 0.0
        for a in range(A):
            W += h[a]
        if rec == 1 and t % 12 == 0 and yr < n_years:
            y_w[j, yr] = W

        # ---- planned flows -------------------------------------------------------------
        draw = 0.0      # desired portfolio-funded spending this month
        contrib = 0.0   # new money into the portfolio this month
        cons_other = 0.0
        if spend_mode == SP_SIGNED:
            f = fp[F_Q] * fp[F_WREF] / 12.0
            if f >= 0.0:
                draw = f
            else:
                contrib = -f
            cons_other = y + p
        elif g >= retire_m:
            ms = g - retire_m
            if spend == 0.0 and (ms == 0 or (t == 0 and t0 > 0)):
                if spend_mode == SP_AMORTIZED:
                    spend = amort[t] * W
                else:
                    spend = fp[F_RATE] * W
            elif ms % 12 == 0:
                if spend_mode == SP_FIXED_PCT:
                    spend = fp[F_RATE] * W
                elif spend_mode == SP_AMORTIZED:
                    spend = amort[t] * W
                elif spend_mode == SP_GUARDRAILS and W > 0.0:
                    cur = spend / W
                    if cur > fp[F_GUP] * fp[F_RATE]:
                        spend = spend * (1.0 - fp[F_GSTEP])
                    elif cur < fp[F_GLO] * fp[F_RATE]:
                        spend = spend * (1.0 + fp[F_GSTEP])
            draw = spend / 12.0
            cons_other = y + p
        else:
            contrib = fp[F_SAVE] * y
            cons_other = (1.0 - fp[F_SAVE]) * y + p

        funded = draw if draw <= W else W
        unmet = draw - funded
        if unmet > 1e-9:
            if first < 0:
                first = t
            unmet_tot += unmet
        des_tot += draw
        fund_tot += funded
        contrib_tot += contrib

        # ---- fund the withdrawal --------------------------------------------------------
        if funded > 0.0 and W > 0.0:
            for a in range(A):
                sell[a] = 0.0
            if cf_mode == CF_CASH_FIRST and cash >= 0:
                s = min(h[cash], funded)
                sell[cash] = s
                rest = funded - s
                if rest > 0.0:
                    base = W - h[cash]
                    for a in range(A):
                        if a != cash and base > 0.0:
                            sell[a] = rest * h[a] / base
            elif cf_mode == CF_BOND_FIRST:
                dsum = 0.0
                for a in range(A):
                    dsum += h[a] * defensive[a]
                s = min(dsum, funded)
                for a in range(A):
                    if defensive[a] > 0.0 and dsum > 0.0:
                        sell[a] = s * h[a] / dsum
                rest = funded - s
                if rest > 0.0:
                    base = W - dsum
                    for a in range(A):
                        if defensive[a] == 0.0 and base > 0.0:
                            sell[a] = rest * h[a] / base
            elif cf_mode == CF_TARGETING or cf_mode == CF_OVERWEIGHT:
                wa = W - funded
                exs = 0.0
                for a in range(A):
                    e = h[a] - tgt[a] * wa
                    tr[a] = e if e > 0.0 else 0.0
                    exs += tr[a]
                if exs >= funded:
                    for a in range(A):
                        sell[a] = funded * tr[a] / exs
                else:
                    base = W - exs
                    for a in range(A):
                        sell[a] = tr[a] + (funded - exs) * (h[a] - tr[a]) / max(base, 1e-12)
            else:
                for a in range(A):
                    sell[a] = funded * h[a] / W
            c = 0.0
            for a in range(A):
                h[a] -= sell[a]
                if h[a] < 0.0:
                    h[a] = 0.0
                cc = _trade_cost(sell[a], comm, spr, 0.0, slsc)
                cl = slip * sell[a] * sell[a] / slsc
                c += cc + cl
                cost_c += abs(sell[a]) * comm
                cost_s += abs(sell[a]) * spr
                cost_l += cl
                if trace:
                    t_trade[t, a] -= sell[a]
            flow_turn += funded
            W = W - funded
            if c > 0.0 and W > 0.0:
                for a in range(A):
                    h[a] -= c * h[a] / W
                W -= c
                cost_tot += c
                if trace:
                    t_cost[t] += c
        # ---- invest the contribution ----------------------------------------------------
        if contrib > 0.0:
            for a in range(A):
                sell[a] = 0.0
            if cf_mode == CF_TARGETING:
                dsum = 0.0
                for a in range(A):
                    d = tgt[a] * (W + contrib) - h[a]
                    tr[a] = d if d > 0.0 else 0.0
                    dsum += tr[a]
                if dsum >= contrib:
                    for a in range(A):
                        sell[a] = contrib * tr[a] / dsum
                else:
                    for a in range(A):
                        sell[a] = tr[a] + (contrib - dsum) * tgt[a]
            else:
                for a in range(A):
                    sell[a] = contrib * tgt[a]
            c = 0.0
            for a in range(A):
                h[a] += sell[a]
                cl = slip * sell[a] * sell[a] / slsc
                c += sell[a] * (comm + spr) + cl
                cost_c += sell[a] * comm
                cost_s += sell[a] * spr
                cost_l += cl
                if trace:
                    t_trade[t, a] += sell[a]
            flow_turn += contrib
            W += contrib
            if c > 0.0 and W > 0.0:
                for a in range(A):
                    h[a] -= c * h[a] / W
                W -= c
                cost_tot += c
                if trace:
                    t_cost[t] += c

        # ---- reserve-adjusted target (cash buffer of reserve_years of desired draws) -------
        if fp[F_RESERVE] > 0.0 and cash >= 0 and W > 0.0 and g >= retire_m:
            res = fp[F_RESERVE] * spend
            rs = min(res / W, 1.0)
            for a in range(A):
                tgt[a] = (1.0 - rs) * tgt[a]
            tgt[cash] += rs

        # ---- trading decision ------------------------------------------------------------
        for a in range(A):
            w[a] = h[a] / W if W > 0.0 else 0.0
        if trace:
            for a in range(A):
                t_pre[t, a] = w[a]
                t_tgt[t, a] = tgt[a]
        reason = RS_NONE
        if W > 0.0 and g > 0:
            if trade_mode == TR_CALENDAR:
                if g % cadence == 0:
                    reason = RS_CALENDAR
            elif trade_mode == TR_ABS_BAND:
                if g % check == 0:
                    for a in range(A):
                        if abs(w[a] - tgt[a]) > fp[F_ABS] + 1e-12:
                            reason = RS_BAND
            elif trade_mode == TR_REL_BAND:
                if g % check == 0:
                    for a in range(A):
                        if tgt[a] > 0.0 and abs(w[a] - tgt[a]) > fp[F_REL] * tgt[a] + 1e-12:
                            reason = RS_BAND
            elif trade_mode == TR_BROWNE:
                if g % check == 0:
                    for a in range(A):
                        if tgt[a] > 0.0 and (w[a] < fp[F_FLOOR] - 1e-12 or w[a] > fp[F_CEIL] + 1e-12):
                            reason = RS_BROWNE
            elif trade_mode == TR_RISK_BAND or trade_mode == TR_UTILITY:
                if g % check == 0:
                    vw = 0.0
                    vt = 0.0
                    vd = 0.0
                    for a in range(A):
                        for b in range(A):
                            vw += w[a] * cov[a, b] * w[b]
                            vt += tgt[a] * cov[a, b] * tgt[b]
                            vd += (w[a] - tgt[a]) * cov[a, b] * (w[b] - tgt[b])
                    if trade_mode == TR_RISK_BAND:
                        if vt > 0.0 and abs(np.sqrt(vw) - np.sqrt(vt)) > fp[F_RISK] * np.sqrt(vt):
                            reason = RS_RISK
                    else:
                        gain = 0.5 * gamma * vd * fp[F_REVIEW] * W
                        est = 0.0
                        for a in range(A):
                            est += _trade_cost((tgt[a] - w[a]) * W, comm, spr, slip, slsc)
                        if vd > 1e-14:
                            if gain > est:
                                reason = RS_UTILITY
                                acc += 1
                            else:
                                rej += 1
                                if trace:
                                    t_reason[t] = RS_REJECTED
        if reason != RS_NONE:
            # band-edge variant: move breached sleeves to the band edge, others scaled pro rata
            if to_edge == 1 and trade_mode == TR_ABS_BAND:
                fixed = 0.0
                free = 0.0
                for a in range(A):
                    if w[a] > tgt[a] + fp[F_ABS]:
                        tr[a] = tgt[a] + fp[F_ABS]
                        fixed += tr[a]
                    elif w[a] < tgt[a] - fp[F_ABS]:
                        tr[a] = max(tgt[a] - fp[F_ABS], 0.0)
                        fixed += tr[a]
                    else:
                        tr[a] = -1.0
                        free += w[a]
                for a in range(A):
                    if tr[a] < 0.0:
                        tr[a] = (1.0 - fixed) * w[a] / free if free > 0.0 else 0.0
            else:
                for a in range(A):
                    tr[a] = tgt[a]
            c = 0.0
            for _it in range(4):
                cn = 0.0
                for a in range(A):
                    cn += _trade_cost(tr[a] * (W - c) - h[a], comm, spr, slip, slsc)
                c = cn
            tn = 0.0
            for a in range(A):
                d = tr[a] * (W - c) - h[a]
                tn += abs(d)
                cost_c += abs(d) * comm
                cost_s += abs(d) * spr
                cost_l += slip * d * d / slsc
                if trace:
                    t_trade[t, a] += d
                h[a] = tr[a] * (W - c)
            turn += tn / W
            if rec == 1 and yr < n_years:
                y_turn[j, yr] += tn / W
            ntr += 1
            cost_tot += c
            W -= c
            if trace:
                t_cost[t] += c
        if trace:
            if reason != RS_NONE:
                t_reason[t] = reason
            for a in range(A):
                t_post[t, a] = h[a] / W if W > 0.0 else 0.0
            t_flow[t, 0] = draw
            t_flow[t, 1] = funded
            t_flow[t, 2] = contrib
            t_flow[t, 3] = cons_other
            t_wealth[t] = W

        if rec == 1 and t % 12 == 0 and yr < n_years:
            for a in range(A):
                y_wts[j, yr, a] = h[a] / W if W > 0.0 else 0.0
            if cash >= 0 and draw > 0.0:
                y_run[j, yr] = h[cash] / draw
            elif cash >= 0:
                y_run[j, yr] = -1.0

        # ---- consumption utility ---------------------------------------------------------
        c_m = funded + cons_other
        cu = c_m if c_m > ufloor else ufloor
        util += disc[t] * _crra(cu / scale, gamma)
        if rec == 1 and yr < n_years:
            y_c[j, yr] += c_m
            y_un[j, yr] += unmet
            y_des[j, yr] += draw + cons_other

        # ---- earn next-period returns ----------------------------------------------------
        Wn = 0.0
        for a in range(A):
            h[a] = h[a] * (1.0 + R[j, t, a])
            if h[a] < 0.0:
                h[a] = 0.0
            Wn += h[a]
        if W > 0.0:
            idx *= Wn / W
            if idx > peak:
                peak = idx
            dd = idx / peak - 1.0
            if dd < mdd:
                mdd = dd
        if fp[F_ETA] > 0.0:
            util += fp[F_ETA] * beq[t] * _crra((Wn + fp[F_KSHIFT]) / scale, gamma)
        W = Wn
    if rec == 1 and n_years < y_w.shape[1]:
        y_w[j, n_years] = W
    for a in range(A):
        h_out[j, a] = h[a]
    s_out[j] = spend
    o_u[j] = util
    o_first[j] = first
    o_unmet[j] = unmet_tot
    o_desired[j] = des_tot
    o_funded[j] = fund_tot
    o_term[j] = W
    o_mdd[j] = mdd
    o_turn[j] = turn
    o_ntr[j] = ntr
    o_cost[j] = cost_tot
    o_costc[j] = cost_c
    o_costs[j] = cost_s
    o_costl[j] = cost_l
    o_flowturn[j] = flow_turn
    o_acc[j] = acc
    o_rej[j] = rej
    o_contrib[j] = contrib_tot


@njit(parallel=True, cache=True)
def _kernel(R, dec_regime, labor, pension, wtgt_sched, defensive, cov, amort, ip, fp, disc, beq, h0, h_out, s_out,
            o_u, o_first, o_unmet, o_desired, o_funded, o_term, o_mdd, o_turn, o_ntr, o_cost, o_costc, o_costs,
            o_costl, o_flowturn, o_acc, o_rej, o_contrib,
            y_w, y_c, y_un, y_des, y_run, y_wts, y_turn,
            t_pre, t_post, t_tgt, t_trade, t_cost, t_flow, t_reason, t_wealth):
    N = R.shape[0]
    for j in prange(N):
        _path(j, R, dec_regime, labor, pension, wtgt_sched, defensive, cov, amort, ip, fp, disc, beq, h0, h_out, s_out,
              o_u, o_first, o_unmet, o_desired, o_funded, o_term, o_mdd, o_turn, o_ntr, o_cost, o_costc, o_costs,
              o_costl, o_flowturn, o_acc, o_rej, o_contrib,
              y_w, y_c, y_un, y_des, y_run, y_wts, y_turn,
              t_pre, t_post, t_tgt, t_trade, t_cost, t_flow, t_reason, t_wealth)


@dataclass
class TradingSpec:
    """Execution layer, decoupled from the target allocation and the spending rule (brief 7.1)."""
    mode: str = "calendar"            # key of TRADE_MODES
    cadence_months: int = 12
    check_months: int = 1             # monitoring frequency for band / Browne rules (12 = annual review)
    abs_band: float = 0.05
    rel_band: float = 0.20
    floor: float = 0.15
    ceiling: float = 0.35
    to_band_edge: bool = False
    funding: str = "proportional"     # key of FUNDING_MODES
    reserve_years: float = 0.0
    commission_bps: float = 0.0
    half_spread_bps: float = 0.0
    slippage_bps: float = 0.0         # bps per $1m of single-asset trade notional (quadratic impact)
    risk_threshold: float = 0.10
    review_months: float = 12.0


@dataclass
class LedgerConfig:
    w0: float
    retire_m: int
    spend_mode: int
    rate: float
    savings_rate: float
    sched: NDArray[np.float64]        # (T, K, A) target weights by decision regime
    trading: TradingSpec
    disc: NDArray[np.float64]
    beq: NDArray[np.float64]
    gamma: float = 4.0
    eta: float = 0.0
    k_shift: float = 10_000.0
    scale: float = 1000.0
    util_floor_monthly: float = 250.0  # utility evaluated at max(consumption, floor); not counted as funded
    w_ref: float = 1_000_000.0
    q_signed: float = 0.0
    amort: NDArray[np.float64] | None = None
    defensive: NDArray[np.float64] | None = None
    cash_index: int = -1
    cov: NDArray[np.float64] | None = None
    guard_upper: float = 1.2
    guard_lower: float = 0.8
    guard_step: float = 0.1
    record_years: bool = True
    trace_path: int = -1
    # sequential execution (historical replay): start from these dollar holdings at global month t0,
    # carrying the annual spending level. Defaults reproduce whole-horizon runs exactly.
    h0: NDArray[np.float64] | None = None    # (N, A) starting holdings; None -> invest w0 at the first target
    t0: int = 0
    spend0: float = 0.0


@dataclass
class LedgerOutput:
    utility: NDArray[np.float64]
    first_shortfall: NDArray[np.int64]     # month index of the first unmet desired draw, -1 if never
    unmet: NDArray[np.float64]             # cumulative unmet real spending ($, monthly units summed)
    desired: NDArray[np.float64]
    funded: NDArray[np.float64]
    contributions: NDArray[np.float64]
    terminal: NDArray[np.float64]
    max_drawdown: NDArray[np.float64]
    turnover: NDArray[np.float64]          # sum over rebalances of one-sided-sum |trade| / W
    n_trades: NDArray[np.int64]
    cost: NDArray[np.float64]
    cost_commission: NDArray[np.float64]
    cost_spread: NDArray[np.float64]
    cost_slippage: NDArray[np.float64]
    flow_notional: NDArray[np.float64]
    accepted: NDArray[np.int64]
    rejected: NDArray[np.int64]
    wealth_y: NDArray[np.float64]
    cons_y: NDArray[np.float64]
    unmet_y: NDArray[np.float64]
    desired_y: NDArray[np.float64]
    runway_y: NDArray[np.float64]
    weights_y: NDArray[np.float64]
    turnover_y: NDArray[np.float64]
    sum_disc: float
    trace: dict[str, NDArray[np.float64]] = field(default_factory=dict)
    holdings_end: NDArray[np.float64] | None = None   # (N, A) dollar holdings after the last month's returns
    spend_end: NDArray[np.float64] | None = None      # (N,) annual spending level after the last month


def simulate(R: NDArray[np.float64], dec_regime: NDArray[np.int64], labor: NDArray[np.float64],
             pension: NDArray[np.float64], cfg: LedgerConfig) -> LedgerOutput:
    N, T, A = R.shape
    if cfg.sched.shape[0] < T:
        raise ValueError("target schedule shorter than the horizon")
    sched = np.ascontiguousarray(cfg.sched[:T], dtype=np.float64)
    if np.any(sched < -1e-12) or np.any(np.abs(sched.sum(axis=2) - 1.0) > 1e-6):
        raise ValueError("target weights must be long-only and sum to one")
    tr = cfg.trading
    ip = np.zeros(N_IP, dtype=np.int64)
    ip[I_RETIRE] = cfg.retire_m
    ip[I_SPEND] = cfg.spend_mode
    ip[I_TRADE] = TRADE_MODES[tr.mode]
    ip[I_CADENCE] = tr.cadence_months
    ip[I_CHECK] = tr.check_months
    ip[I_CF] = FUNDING_MODES[tr.funding]
    ip[I_CASH] = cfg.cash_index
    ip[I_EDGE] = 1 if tr.to_band_edge else 0
    ip[I_REC] = 1 if cfg.record_years else 0
    ip[I_TRACE] = cfg.trace_path
    ip[I_T0] = cfg.t0
    fp = np.zeros(N_FP)
    fp[F_W0] = cfg.w0
    fp[F_RATE] = cfg.rate
    fp[F_SAVE] = cfg.savings_rate
    fp[F_GUP] = cfg.guard_upper
    fp[F_GLO] = cfg.guard_lower
    fp[F_GSTEP] = cfg.guard_step
    fp[F_ABS] = tr.abs_band
    fp[F_REL] = tr.rel_band
    fp[F_FLOOR] = tr.floor
    fp[F_CEIL] = tr.ceiling
    fp[F_COMM] = tr.commission_bps / 1e4
    fp[F_SPREAD] = tr.half_spread_bps / 1e4
    fp[F_SLIP] = tr.slippage_bps / 1e4
    fp[F_SLIPSCALE] = 1e6
    fp[F_RESERVE] = tr.reserve_years
    fp[F_GAMMA] = cfg.gamma
    fp[F_ETA] = cfg.eta
    fp[F_KSHIFT] = cfg.k_shift
    fp[F_SCALE] = cfg.scale
    fp[F_UFLOOR] = cfg.util_floor_monthly
    fp[F_WREF] = cfg.w_ref
    fp[F_Q] = cfg.q_signed
    fp[F_RISK] = tr.risk_threshold
    fp[F_REVIEW] = tr.review_months
    fp[F_SPEND0] = cfg.spend0
    if tr.reserve_years > 0 and cfg.cash_index < 0:
        raise ValueError("a cash reserve needs a cash sleeve in the universe")
    if tr.funding == "cash_first" and cfg.cash_index < 0:
        raise ValueError("cash-first funding needs a cash sleeve in the universe")
    defensive = cfg.defensive if cfg.defensive is not None else np.zeros(A)
    cov = cfg.cov if cfg.cov is not None else np.zeros((A, A))
    amort = cfg.amort if cfg.amort is not None else np.zeros(T)
    Y = (T + 11) // 12 if cfg.record_years else 1
    Nr = N if cfg.record_years else 1
    Tt = T if cfg.trace_path >= 0 else 1
    f = lambda *s: np.zeros(s)  # noqa: E731
    o = dict(u=f(N), first=np.zeros(N, dtype=np.int64), unmet=f(N), desired=f(N), funded=f(N), term=f(N), mdd=f(N),
             turn=f(N), ntr=np.zeros(N, dtype=np.int64), cost=f(N), costc=f(N), costs=f(N), costl=f(N),
             flowturn=f(N), acc=np.zeros(N, dtype=np.int64), rej=np.zeros(N, dtype=np.int64), contrib=f(N))
    yy = dict(w=f(Nr, Y + 1), c=f(Nr, Y), un=f(Nr, Y), des=f(Nr, Y), run=f(Nr, Y), wts=f(Nr, Y, A), turn=f(Nr, Y))
    h0 = np.zeros((N, A)) if cfg.h0 is None else np.ascontiguousarray(cfg.h0, dtype=np.float64)
    if h0.shape != (N, A) or np.any(h0 < 0):
        raise ValueError("h0 must be non-negative dollar holdings of shape (N, A)")
    h_out = np.zeros((N, A))
    s_out = np.zeros(N)
    tt = dict(pre=f(Tt, A), post=f(Tt, A), tgt=f(Tt, A), trade=f(Tt, A), cost=f(Tt), flow=f(Tt, 4),
              reason=np.zeros(Tt, dtype=np.int64), wealth=f(Tt))
    _kernel(np.ascontiguousarray(R, dtype=np.float64), np.ascontiguousarray(dec_regime[:, :T], dtype=np.int64),
            np.ascontiguousarray(labor[:, :T], dtype=np.float64), np.ascontiguousarray(pension[:, :T], dtype=np.float64),
            sched, np.ascontiguousarray(defensive, dtype=np.float64), np.ascontiguousarray(cov, dtype=np.float64),
            np.ascontiguousarray(amort[:T], dtype=np.float64), ip, fp,
            np.ascontiguousarray(cfg.disc[:T], dtype=np.float64), np.ascontiguousarray(cfg.beq[:T], dtype=np.float64),
            h0, h_out, s_out,
            o["u"], o["first"], o["unmet"], o["desired"], o["funded"], o["term"], o["mdd"], o["turn"], o["ntr"],
            o["cost"], o["costc"], o["costs"], o["costl"], o["flowturn"], o["acc"], o["rej"], o["contrib"],
            yy["w"], yy["c"], yy["un"], yy["des"], yy["run"], yy["wts"], yy["turn"],
            tt["pre"], tt["post"], tt["tgt"], tt["trade"], tt["cost"], tt["flow"], tt["reason"], tt["wealth"])
    trace = tt if cfg.trace_path >= 0 else {}
    return LedgerOutput(o["u"], o["first"], o["unmet"], o["desired"], o["funded"], o["contrib"], o["term"], o["mdd"],
                        o["turn"], o["ntr"], o["cost"], o["costc"], o["costs"], o["costl"], o["flowturn"], o["acc"],
                        o["rej"], yy["w"], yy["c"], yy["un"], yy["des"], yy["run"], yy["wts"], yy["turn"],
                        float(np.sum(cfg.disc[:T])), trace, h_out, s_out)


def constant_schedule(w: NDArray[np.float64], months: int) -> NDArray[np.float64]:
    return np.broadcast_to(np.asarray(w, dtype=float), (months, 1, len(w))).copy()
