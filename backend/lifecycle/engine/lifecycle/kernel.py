"""Numba path kernel: (scenario tensor, investor, policy) -> path-level consumption, wealth, utility.

Timing (brief 4.1): flows at the start of each month, then the portfolio earns its return
net of proportional rebalancing cost:
    I_t = W_t + Y_t + P_t - C_t
    W_{t+1} = I_t (1 + w_t'R_{t+1}) - kappa ||w_t - w~_t||_1 I_t
If a path cannot fund the floor C_min, consumption is set to C_min, the gap is booked to an
explicit shortfall variable and the path is flagged infeasible.
"""
from dataclasses import dataclass

import numpy as np
from numba import njit, prange
from numpy.typing import NDArray

SPEND_FIXED_REAL = 0
SPEND_FIXED_PCT = 1
SPEND_GUARDRAILS = 2
SPEND_AMORTIZED = 3

WMODE_SCHEDULE = 0
WMODE_PARAMETRIC = 1
WMODE_BUCKET = 2

SPEND_CODES = {"fixed_real": SPEND_FIXED_REAL, "fixed_pct": SPEND_FIXED_PCT, "guardrails": SPEND_GUARDRAILS,
               "utility_optimal": SPEND_AMORTIZED, "amortized": SPEND_AMORTIZED, "bucket": SPEND_FIXED_REAL}


@njit(cache=True)
def _path(j, R, regime, labor, pension, w0, retire_m, spend_rule, rate, g_upper, g_lower, g_step, amort,
          savings_rate, wmode, wsched, risky_w, safe_w, theta, bucket_years, start_age, ref_age, risky_mask,
          rebalance_every, kappa, disc, beq, gamma, eta, c_min, k_shift, scale, w_ref,
          out_u, out_uc, out_short, out_deplete, out_infeas, out_svar, out_turn,
          out_wy, out_cy, out_ry, out_qy, out_wts):
    T = R.shape[1]
    A = R.shape[2]
    K = wsched.shape[1]
    n_years = out_cy.shape[1]
    if j >= 0:
        W = w0
        wcur = np.zeros(A)
        wtgt = np.zeros(A)
        have_w = False
        spend = 0.0
        util_c = 0.0
        util_b = 0.0
        L = 0.0
        dep = -1
        infeas = 0
        svar = 0.0
        turn_tot = 0.0
        for t in range(T):
            yr = t // 12
            y = labor[j, t]
            p = pension[j, t]
            if t % 12 == 0 and yr < n_years:
                out_wy[j, yr] = W
            if t >= retire_m:
                ms = t - retire_m
                if ms == 0:
                    if spend_rule == SPEND_AMORTIZED:
                        spend = amort[t] * W
                    else:
                        spend = rate * W
                elif ms % 12 == 0:
                    if spend_rule == SPEND_FIXED_PCT:
                        spend = rate * W
                    elif spend_rule == SPEND_AMORTIZED:
                        spend = amort[t] * W
                    elif spend_rule == SPEND_GUARDRAILS:
                        if W > 0.0:
                            cur = spend / W
                            if cur > g_upper * rate:
                                spend = spend * (1.0 - g_step)
                            elif cur < g_lower * rate:
                                spend = spend * (1.0 + g_step)
                creq = spend / 12.0 + p + y
            else:
                creq = (1.0 - savings_rate) * y + p
            if creq < c_min:
                creq = c_min  # the consumption floor is a hard lower bound on planned spending
            avail = W + y + p
            if avail >= creq - 1e-6:
                c = creq
                funded = creq
            elif avail >= c_min:
                c = avail
                funded = avail
            else:
                c = c_min
                funded = avail
                infeas = 1
                svar += c_min - avail
            if creq > 0.0 and funded < creq - 1e-6:
                L += (creq - funded) / creq
                if dep < 0:
                    dep = t
            inv = avail - c
            if inv < 0.0:
                inv = 0.0

            age = start_age + t / 12.0
            if wmode == WMODE_SCHEDULE:
                k = 0
                if K > 1:
                    k = regime[j, t]
                    if k >= K:
                        k = K - 1
                    if k < 0:
                        k = 0
                for a in range(A):
                    wtgt[a] = wsched[t, k, a]
            else:
                alpha = -1.0
                if wmode == WMODE_PARAMETRIC:
                    x = inv / max(12.0 * creq, 1e-9)
                    flag = 1.0 if regime[j, t] > 0 else 0.0
                    z = (theta[0] + theta[1] * (age - ref_age) / 10.0
                         + theta[2] * (np.log(max(x, 1e-6)) - np.log(25.0)) + theta[3] * flag)
                    alpha = min(max(z, 0.0), 1.0)
                else:
                    if t >= retire_m:
                        if inv > 0.0:
                            alpha = 1.0 - min(1.0, bucket_years * spend / inv)
                        else:
                            alpha = 0.0
                if alpha >= 0.0:
                    for a in range(A):
                        wtgt[a] = alpha * risky_w[a] + (1.0 - alpha) * safe_w[a]
                else:
                    for a in range(A):
                        wtgt[a] = wsched[t, 0, a]

            turnover = 0.0
            if (not have_w) or (t % rebalance_every == 0):
                if have_w:
                    for a in range(A):
                        turnover += abs(wtgt[a] - wcur[a])
                for a in range(A):
                    wcur[a] = wtgt[a]
                have_w = True
            turn_tot += turnover

            if t % 12 == 0 and yr < n_years:
                rs = 0.0
                for a in range(A):
                    out_wts[j, yr, a] = wcur[a]
                    rs += wcur[a] * risky_mask[a]
                out_ry[j, yr] = rs

            pr = 0.0
            for a in range(A):
                pr += wcur[a] * R[j, t, a]
            Wn = inv * (1.0 + pr) - kappa * turnover * inv
            if Wn < 0.0:
                Wn = 0.0
            g = 1.0 + pr
            if g > 1e-12:
                for a in range(A):
                    wcur[a] = wcur[a] * (1.0 + R[j, t, a]) / g

            cs = c / scale
            if gamma == 1.0:
                uc = np.log(cs)
            else:
                uc = cs ** (1.0 - gamma) / (1.0 - gamma)
            util_c += disc[t] * uc
            if eta > 0.0:
                bs = (Wn + k_shift) / scale
                if gamma == 1.0:
                    ub = np.log(bs)
                else:
                    ub = bs ** (1.0 - gamma) / (1.0 - gamma)
                util_b += eta * beq[t] * ub
            if yr < n_years:
                out_cy[j, yr] += c
                out_qy[j, yr] += (c - y - p) / w_ref
            W = Wn
        if n_years < out_wy.shape[1]:
            out_wy[j, n_years] = W
        out_u[j] = util_c + util_b
        out_uc[j] = util_c
        out_short[j] = L
        out_deplete[j] = dep
        out_infeas[j] = infeas
        out_svar[j] = svar
        out_turn[j] = turn_tot


@njit(parallel=True, cache=True)
def _kernel(R, regime, labor, pension, w0, retire_m, spend_rule, rate, g_upper, g_lower, g_step, amort,
            savings_rate, wmode, wsched, risky_w, safe_w, theta, bucket_years, start_age, ref_age, risky_mask,
            rebalance_every, kappa, disc, beq, gamma, eta, c_min, k_shift, scale, w_ref,
            out_u, out_uc, out_short, out_deplete, out_infeas, out_svar, out_turn,
            out_wy, out_cy, out_ry, out_qy, out_wts):
    N = R.shape[0]
    for j in prange(N):
        _path(j, R, regime, labor, pension, w0, retire_m, spend_rule, rate, g_upper, g_lower, g_step, amort,
              savings_rate, wmode, wsched, risky_w, safe_w, theta, bucket_years, start_age, ref_age, risky_mask,
              rebalance_every, kappa, disc, beq, gamma, eta, c_min, k_shift, scale, w_ref,
              out_u, out_uc, out_short, out_deplete, out_infeas, out_svar, out_turn,
              out_wy, out_cy, out_ry, out_qy, out_wts)


@dataclass
class KernelConfig:
    w0: float
    retire_m: int
    spend_rule: int
    rate: float
    savings_rate: float
    wmode: int
    sched: NDArray[np.float64]        # (T, K, A)
    risky_w: NDArray[np.float64]      # (A,)
    safe_w: NDArray[np.float64]       # (A,)
    theta: NDArray[np.float64]        # (4,)
    bucket_years: float
    start_age: float
    risky_mask: NDArray[np.float64]   # (A,) 1 for growth assets
    rebalance_every: int
    kappa: float
    disc: NDArray[np.float64]         # (T,)
    beq: NDArray[np.float64]          # (T,)
    gamma: float
    eta: float
    c_min: float                      # monthly
    k_shift: float
    scale: float
    w_ref: float
    amort: NDArray[np.float64]        # (T,)
    ref_age: float = 65.0
    g_upper: float = 1.2
    g_lower: float = 0.8
    g_step: float = 0.1


@dataclass
class SimOutput:
    utility: NDArray[np.float64]       # (N,) total path utility (consumption + bequest)
    utility_c: NDArray[np.float64]     # (N,) consumption part
    shortfall: NDArray[np.float64]     # (N,) normalised shortfall L_j
    deplete_month: NDArray[np.int64]   # (N,) first month with unfunded spending, -1 if never
    infeasible: NDArray[np.int64]      # (N,) 1 if C_min could not be funded
    shortfall_var: NDArray[np.float64]
    turnover: NDArray[np.float64]
    wealth_y: NDArray[np.float64]      # (N, Y+1) wealth at the start of each year (and final)
    cons_y: NDArray[np.float64]        # (N, Y) annual consumption
    risky_y: NDArray[np.float64]       # (N, Y) growth-asset share at the start of each year
    q_y: NDArray[np.float64]           # (N, Y) annual signed net-flow rate
    weights_y: NDArray[np.float64]     # (N, Y, A)
    sum_disc: float


def simulate(R: NDArray[np.float64], regime: NDArray[np.int64], labor: NDArray[np.float64],
             pension: NDArray[np.float64], cfg: KernelConfig) -> SimOutput:
    N, T, A = R.shape
    n_years = (T + 11) // 12
    out_u = np.zeros(N)
    out_uc = np.zeros(N)
    out_short = np.zeros(N)
    out_dep = np.zeros(N, dtype=np.int64)
    out_inf = np.zeros(N, dtype=np.int64)
    out_svar = np.zeros(N)
    out_turn = np.zeros(N)
    out_wy = np.zeros((N, n_years + 1))
    out_cy = np.zeros((N, n_years))
    out_ry = np.zeros((N, n_years))
    out_qy = np.zeros((N, n_years))
    out_wts = np.zeros((N, n_years, A))
    if cfg.sched.shape[0] < T:
        raise ValueError("weight schedule shorter than the horizon")
    _kernel(np.ascontiguousarray(R), np.ascontiguousarray(regime), np.ascontiguousarray(labor),
            np.ascontiguousarray(pension), float(cfg.w0), int(cfg.retire_m), int(cfg.spend_rule), float(cfg.rate),
            float(cfg.g_upper), float(cfg.g_lower), float(cfg.g_step), np.ascontiguousarray(cfg.amort[:T]),
            float(cfg.savings_rate), int(cfg.wmode), np.ascontiguousarray(cfg.sched[:T]),
            np.ascontiguousarray(cfg.risky_w), np.ascontiguousarray(cfg.safe_w),
            np.ascontiguousarray(cfg.theta, dtype=np.float64), float(cfg.bucket_years), float(cfg.start_age),
            float(cfg.ref_age), np.ascontiguousarray(cfg.risky_mask), max(int(cfg.rebalance_every), 1),
            float(cfg.kappa), np.ascontiguousarray(cfg.disc[:T]), np.ascontiguousarray(cfg.beq[:T]),
            float(cfg.gamma), float(cfg.eta), float(cfg.c_min), float(cfg.k_shift), float(cfg.scale),
            float(cfg.w_ref), out_u, out_uc, out_short, out_dep, out_inf, out_svar, out_turn,
            out_wy, out_cy, out_ry, out_qy, out_wts)
    return SimOutput(out_u, out_uc, out_short, out_dep, out_inf, out_svar, out_turn, out_wy, out_cy, out_ry,
                     out_qy, out_wts, float(np.sum(cfg.disc[:T])))
