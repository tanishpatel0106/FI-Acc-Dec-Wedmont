"""CRRA utility, certainty-equivalent consumption and delta-method standard errors (brief 4.3-4.4)."""
import numpy as np
from numpy.typing import NDArray


def crra(c: NDArray[np.float64] | float, gamma: float) -> NDArray[np.float64] | float:
    if gamma == 1.0:
        return np.log(c)
    return np.power(c, 1.0 - gamma) / (1.0 - gamma)


def ce_from_utility(u: float, gamma: float, sum_disc: float) -> float:
    """Constant per-period consumption with the same survival-weighted discounted utility."""
    if gamma == 1.0:
        return float(np.exp(u / sum_disc))
    base = (1.0 - gamma) * u / sum_disc
    if base <= 0:
        return 0.0
    return float(base ** (1.0 / (1.0 - gamma)))


def dce_du(ce: float, u: float, gamma: float, sum_disc: float) -> float:
    if gamma == 1.0:
        return ce / sum_disc
    return ce / ((1.0 - gamma) * u)


def ce_with_se(path_u: NDArray[np.float64], gamma: float, sum_disc: float) -> tuple[float, float]:
    n = len(path_u)
    u = float(np.mean(path_u))
    ce = ce_from_utility(u, gamma, sum_disc)
    sd = float(np.std(path_u, ddof=1)) if n > 1 else 0.0
    se = abs(dce_du(ce, u, gamma, sum_disc)) * sd / np.sqrt(n)
    return ce, float(se)


def paired_delta_ce(u_a: NDArray[np.float64], u_b: NDArray[np.float64], gamma: float,
                    sum_disc: float) -> tuple[float, float]:
    """Delta_CE = CE_a / CE_b - 1 with a delta-method SE from paired path utilities (common random numbers)."""
    n = len(u_a)
    ma = float(np.mean(u_a))
    mb = float(np.mean(u_b))
    ce_a = ce_from_utility(ma, gamma, sum_disc)
    ce_b = ce_from_utility(mb, gamma, sum_disc)
    if ce_b <= 0:
        return float("nan"), float("nan")
    delta = ce_a / ce_b - 1.0
    ga = dce_du(ce_a, ma, gamma, sum_disc) / ce_b
    gb = -ce_a / ce_b ** 2 * dce_du(ce_b, mb, gamma, sum_disc)
    if n < 2:
        return float(delta), 0.0
    cov = np.cov(np.vstack([u_a, u_b]))
    var = ga * ga * cov[0, 0] + gb * gb * cov[1, 1] + 2 * ga * gb * cov[0, 1]
    return float(delta), float(np.sqrt(max(var, 0.0) / n))


def path_ce(path_u: NDArray[np.float64], gamma: float, sum_disc: float) -> NDArray[np.float64]:
    """Per-path CE (for scatter plots of paired outcomes)."""
    if gamma == 1.0:
        return np.exp(path_u / sum_disc)
    base = (1.0 - gamma) * path_u / sum_disc
    return np.where(base > 0, np.power(np.maximum(base, 1e-300), 1.0 / (1.0 - gamma)), 0.0)
