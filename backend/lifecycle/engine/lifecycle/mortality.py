"""Survival weights from period life tables (q_x annual, constant monthly hazard within a year)."""
import numpy as np
import pandas as pd
from numpy.typing import NDArray


def monthly_survival(q_by_age: NDArray[np.float64], start_age: float, n_months: int,
                     enabled: bool = True) -> NDArray[np.float64]:
    """S_t for t = 0..n_months (S_0 = 1). Without mortality, S_t = 1 until the horizon."""
    if not enabled:
        return np.ones(n_months + 1)
    S = np.empty(n_months + 1)
    S[0] = 1.0
    for t in range(n_months):
        age = int(np.floor(start_age + t / 12.0))
        age = min(age, len(q_by_age) - 1)
        q = float(q_by_age[age])
        S[t + 1] = S[t] * (1.0 - q) ** (1.0 / 12.0)
    return S


def q_vector(table: pd.DataFrame, sex: str) -> NDArray[np.float64]:
    col = "q_" + sex
    if col not in table.columns:
        col = "q_unisex"
    q = np.zeros(121)
    ages = table["age"].to_numpy(dtype=int)
    vals = table[col].to_numpy(dtype=float)
    for i in range(len(ages)):
        if 0 <= ages[i] <= 120:
            q[ages[i]] = vals[i]
    last = int(ages.max())
    q[last:] = 1.0
    return q


def discount_weights(S: NDArray[np.float64], beta_monthly: float) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """disc_t = beta^t S_t and bequest_t = beta^{t+1} S_t (1 - s_{t+1}) for t = 0..T-1 (death at T)."""
    T = len(S) - 1
    t = np.arange(T)
    disc = beta_monthly ** t * S[:T]
    cond = np.where(S[:T] > 0, S[1:] / np.maximum(S[:T], 1e-300), 0.0)
    cond[-1] = 0.0  # everyone dies at the horizon, so the final wealth is bequeathed
    beq = beta_monthly ** (t + 1) * S[:T] * (1.0 - cond)
    return disc, beq


def life_expectancy(q_by_age: NDArray[np.float64], age: float) -> float:
    S = monthly_survival(q_by_age, age, int((120 - age) * 12))
    return float(S[1:].sum() / 12.0)


def amortization_fractions(q_by_age: NDArray[np.float64], start_age: float, n_months: int,
                           real_rate: float, max_age: float) -> NDArray[np.float64]:
    """Annual withdrawal fraction W / a(age): survival-weighted annuity factor at a real rate.

    Used by the parametric utility-optimal spending rule (theta = real_rate).
    """
    out = np.empty(n_months)
    for t in range(n_months):
        age = start_age + t / 12.0
        years = int(np.ceil(max_age - age))
        if years <= 1:
            out[t] = 1.0
            continue
        surv = 1.0
        factor = 0.0
        for k in range(years):
            factor += surv / (1.0 + real_rate) ** k
            a = min(int(np.floor(age + k)), len(q_by_age) - 1)
            surv *= 1.0 - q_by_age[a]
        out[t] = 1.0 / max(factor, 1.0)
    return out
