"""M2 fixed income: pricing, duration/DV01/convexity, curve PCA, return decomposition, liabilities."""
from typing import Any

import numpy as np
from numpy.typing import NDArray


def cashflows(coupon: float, maturity: float, freq: int = 2) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    n = int(round(maturity * freq))
    times = np.arange(1, n + 1) / freq
    flows = np.full(n, coupon / freq)
    flows[-1] += 1.0
    return times, flows


def price(yld: float, coupon: float, maturity: float, freq: int = 2) -> float:
    t, f = cashflows(coupon, maturity, freq)
    return float(np.sum(f / (1 + yld / freq) ** (t * freq)))


def macaulay_duration(yld: float, coupon: float, maturity: float, freq: int = 2) -> float:
    t, f = cashflows(coupon, maturity, freq)
    pv = f / (1 + yld / freq) ** (t * freq)
    return float(np.sum(t * pv) / np.sum(pv))


def modified_duration(yld: float, coupon: float, maturity: float, freq: int = 2) -> float:
    return macaulay_duration(yld, coupon, maturity, freq) / (1 + yld / freq)


def convexity(yld: float, coupon: float, maturity: float, freq: int = 2) -> float:
    t, f = cashflows(coupon, maturity, freq)
    k = t * freq
    pv = f / (1 + yld / freq) ** k
    return float(np.sum(pv * k * (k + 1)) / (np.sum(pv) * freq ** 2 * (1 + yld / freq) ** 2))


def dv01(yld: float, coupon: float, maturity: float, freq: int = 2) -> float:
    """Price change per 1bp, per 100 face."""
    return modified_duration(yld, coupon, maturity, freq) * price(yld, coupon, maturity, freq) * 100 * 1e-4


def approx_return(d_mod: float, conv: float, dy: float) -> float:
    return -d_mod * dy + 0.5 * conv * dy * dy


def risk_table(par_yields: dict[float, float]) -> list[dict[str, float]]:
    rows = []
    for m, y in sorted(par_yields.items()):
        rows.append({"maturity": m, "yield": y, "mac_duration": macaulay_duration(y, y, m),
                     "mod_duration": modified_duration(y, y, m), "convexity": convexity(y, y, m),
                     "dv01": dv01(y, y, m)})
    return rows


def zero_to_par(zero: NDArray[np.float64], maturities: NDArray[np.float64], freq: int = 2) -> dict[float, float]:
    """Par yields from continuously-compounded zero yields (GSW) at the given annual maturities."""
    out = {}
    for m in maturities:
        t = np.arange(1, int(round(m * freq)) + 1) / freq
        z = np.interp(t, maturities, zero)
        d = np.exp(-z * t)
        out[float(m)] = float(freq * (1 - d[-1]) / d.sum())
    return out


def price_on_curve(coupon: float, maturity: float, zero_m: NDArray[np.float64], zero_y: NDArray[np.float64],
                   shift: NDArray[np.float64] | float = 0.0, freq: int = 2) -> float:
    t, f = cashflows(coupon, maturity, freq)
    z = np.interp(t, zero_m, zero_y + shift)
    return float(np.sum(f * np.exp(-z * t)))


def shock_table(zero_m: NDArray[np.float64], zero_y: NDArray[np.float64], maturities: list[float],
                shocks_bp: list[float]) -> list[dict[str, Any]]:
    """Parallel-shock P&L: full repricing on the zero curve vs duration+convexity approximation."""
    par = zero_to_par(zero_y, zero_m)
    rows = []
    for m in maturities:
        y = float(np.interp(m, list(par.keys()), list(par.values())))
        p0 = price_on_curve(y, m, zero_m, zero_y)
        dm = modified_duration(y, y, m)
        cx = convexity(y, y, m)
        for s in shocks_bp:
            full = price_on_curve(y, m, zero_m, zero_y, s / 1e4) / p0 - 1
            rows.append({"maturity": m, "shock_bp": s, "full": full, "approx": approx_return(dm, cx, s / 1e4),
                         "error_bp": (approx_return(dm, cx, s / 1e4) - full) * 1e4})
    return rows


def twist(zero_m: NDArray[np.float64], bp_short: float, bp_long: float, pivot: float = 5.0) -> NDArray[np.float64]:
    return np.interp(zero_m, [zero_m.min(), pivot, zero_m.max()], [bp_short, 0.0, bp_long]) / 1e4


def pca_yield_changes(yields: NDArray[np.float64], n: int = 3) -> dict[str, Any]:
    """PCA on monthly changes; loadings are checked before labelling (level: same sign; slope: monotone)."""
    dy = np.diff(yields, axis=0)
    dy = dy - dy.mean(axis=0)
    cov = np.cov(dy, rowvar=False)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    evals = evals[order]
    evecs = evecs[:, order]
    load = evecs[:, :n].copy()
    if load[:, 0].mean() < 0:
        load[:, 0] *= -1
    if n > 1 and load[-1, 1] - load[0, 1] < 0:
        load[:, 1] *= -1
    if n > 2 and load[len(load) // 2, 2] < 0:
        load[:, 2] *= -1
    labels = []
    same_sign = np.all(load[:, 0] > 0)
    labels.append("level" if same_sign else "factor 1")
    if n > 1:
        diffs = np.diff(load[:, 1])
        labels.append("slope" if np.mean(diffs > 0) > 0.8 else "factor 2")
    if n > 2:
        mid = load[len(load) // 2, 2]
        labels.append("curvature" if mid > 0 and load[0, 2] < mid and load[-1, 2] < mid else "factor 3")
    return {"loadings": load.T, "explained": (evals[:n] / evals.sum()), "labels": labels, "scores": dy @ load,
            "eigenvalues": evals[:n]}


def return_decomposition(zero_m: NDArray[np.float64], curve0: NDArray[np.float64], curve1: NDArray[np.float64],
                         maturity: float) -> dict[str, float]:
    """One-month return of a par bond split into carry, roll-down, yield change and convexity."""
    par0 = zero_to_par(curve0, zero_m)
    y0 = float(np.interp(maturity, list(par0.keys()), list(par0.values())))
    h = 1.0 / 12.0
    p0 = price_on_curve(y0, maturity, zero_m, curve0)
    # roll-down: same curve, one month less to maturity
    t, f = cashflows(y0, maturity)
    t_roll = t - h
    p_roll = float(np.sum(f * np.exp(-np.interp(t_roll, zero_m, curve0) * t_roll)))
    p1 = float(np.sum(f * np.exp(-np.interp(t_roll, zero_m, curve1) * t_roll)))
    carry = y0 * h
    total = (p1 - p0) / p0 + carry
    roll = (p_roll - p0) / p0
    par_roll = zero_to_par(curve0, zero_m)
    y_roll = float(np.interp(maturity - h, list(par_roll.keys()), list(par_roll.values())))
    par1 = zero_to_par(curve1, zero_m)
    y1 = float(np.interp(maturity - h, list(par1.keys()), list(par1.values())))
    dy = y1 - y_roll
    dm = modified_duration(y_roll, y0, maturity - h)
    cx = convexity(y_roll, y0, maturity - h)
    dur_eff = -dm * dy
    conv_eff = 0.5 * cx * dy * dy
    return {"total": total, "carry": carry, "roll_down": roll, "yield_change": dur_eff, "convexity": conv_eff,
            "residual": total - carry - roll - dur_eff - conv_eff, "dy": dy}


def liability_pv_duration(withdrawals: NDArray[np.float64], times: NDArray[np.float64], real_m: NDArray[np.float64],
                          real_zero: NDArray[np.float64]) -> dict[str, float]:
    """PV and Macaulay duration of a real withdrawal stream on the (TIPS) real zero curve."""
    z = np.interp(times, real_m, real_zero)  # flat extrapolation beyond the last real maturity
    d = np.exp(-z * times)
    pv = float(np.sum(withdrawals * d))
    dur = float(np.sum(times * withdrawals * d) / pv) if pv > 0 else 0.0
    return {"pv": pv, "duration": dur}
