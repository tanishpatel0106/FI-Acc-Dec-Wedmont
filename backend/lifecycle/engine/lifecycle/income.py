"""Labor income (Cocco-Gomes-Maenhout 2005) and retirement pension.

ln Y_t = f(age_t) + v_t + eps_t, v_t = v_{t-1} + u_t; permanent shocks may correlate with
equity returns (rho_Ye). Annual parameters are mapped to monthly steps: permanent shocks
accrue monthly with variance sigma_u^2/12; the transitory shock is drawn once per age-year.
Shocks are mean-corrected so E[Y_t] follows the profile.
"""
import numpy as np
from numpy.typing import NDArray


def age_profile(age: NDArray[np.float64], profile: str) -> NDArray[np.float64]:
    if profile == "flat":
        return np.zeros_like(age)
    if profile == "cgm_college":
        return -4.3148 + 0.3194 * age - 0.0577 * age ** 2 / 10 + 0.0033 * age ** 3 / 100
    if profile == "cgm_highschool":
        return -2.1700 + 0.1682 * age - 0.0323 * age ** 2 / 10 + 0.0020 * age ** 3 / 100
    raise ValueError("unknown income profile: " + profile)


def simulate_income(n: int, months: int, start_age: float, retire_age: float, income0: float, profile: str,
                    sigma_u: float, sigma_eps: float, rho_ye: float, equity_z: NDArray[np.float64],
                    replacement: float, pension_override: float | None,
                    rng: np.random.Generator) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Monthly real labor income and pension arrays, both (n, months)."""
    labor = np.zeros((n, months))
    pension = np.zeros((n, months))
    retire_m = int(round((retire_age - start_age) * 12))
    if retire_m <= 0:
        level = pension_override if pension_override is not None else replacement * income0
        pension[:, :] = level / 12.0
        return labor, pension
    ages = start_age + np.arange(months) / 12.0
    f = age_profile(ages, profile) - age_profile(np.array([start_age]), profile)[0]
    su = sigma_u / np.sqrt(12.0)
    z_own = rng.standard_normal((n, months))
    u = su * (rho_ye * equity_z + np.sqrt(max(1.0 - rho_ye ** 2, 0.0)) * z_own) - 0.5 * su * su
    v = np.cumsum(u, axis=1)
    n_years = months // 12 + 1
    eps_y = sigma_eps * rng.standard_normal((n, n_years)) - 0.5 * sigma_eps ** 2
    eps = np.repeat(eps_y, 12, axis=1)[:, :months]
    work = min(retire_m, months)
    labor[:, :work] = income0 / 12.0 * np.exp(f[:work] + v[:, :work] + eps[:, :work])
    if retire_m < months:
        final_perm = income0 * np.exp(f[retire_m - 1] + v[:, retire_m - 1])
        levels = replacement * final_perm if pension_override is None else np.full(n, pension_override)
        pension[:, retire_m:] = (levels / 12.0)[:, None]
    return labor, pension
