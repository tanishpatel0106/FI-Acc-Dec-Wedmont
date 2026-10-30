"""High-level evaluation: investor + preferences + policy on a scenario tensor (common random numbers)."""
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from lifecycle.engine.lifecycle import kernel, mortality
from lifecycle.engine.lifecycle.income import simulate_income
from lifecycle.engine.lifecycle.policies import WeightPolicy, risky_mask
from lifecycle.engine.scenarios.base import ScenarioTensor


@dataclass(frozen=True)
class Investor:
    start_age: float = 65.0
    retirement_age: float = 65.0
    max_age: float = 100.0
    initial_wealth: float = 1_000_000.0
    income: float = 100_000.0          # annual real labor income at start_age
    income_profile: str = "cgm_college"
    sigma_u: float = 0.10
    sigma_eps: float = 0.10
    rho_ye: float = 0.0
    replacement_rate: float = 0.40
    pension: float | None = 20_000.0   # annual real pension; None -> replacement x final permanent income
    savings_rate: float = 0.10
    sex: str = "unisex"
    mortality: bool = True

    @property
    def months(self) -> int:
        return int(round((self.max_age - self.start_age) * 12))

    @property
    def retire_month(self) -> int:
        return max(int(round((self.retirement_age - self.start_age) * 12)), 0)


@dataclass(frozen=True)
class Preferences:
    gamma: float = 4.0
    beta_annual: float = 0.97
    eta: float = 0.0
    c_min: float = 6_000.0             # annual real floor
    bequest_shift: float = 10_000.0


@dataclass(frozen=True)
class Spending:
    rule: str = "fixed_real"
    withdrawal_rate: float = 0.04
    amort_rate: float = 0.02           # real rate theta of the amortised (utility-optimal) rule
    rebalance_months: int = 1
    cost_bps: float = 0.0
    guard_upper: float = 1.2
    guard_lower: float = 0.8
    guard_step: float = 0.1


@dataclass
class Context:
    """Per-(tensor, investor, preferences) precomputations shared by every policy (CRN)."""
    tensor: ScenarioTensor
    investor: Investor
    prefs: Preferences
    labor: NDArray[np.float64]
    pension: NDArray[np.float64]
    disc: NDArray[np.float64]
    beq: NDArray[np.float64]
    survival: NDArray[np.float64]
    q: NDArray[np.float64]
    w_ref: float
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def months(self) -> int:
        return self.tensor.n_months


def build_context(tensor: ScenarioTensor, investor: Investor, prefs: Preferences, q_by_age: NDArray[np.float64],
                  seed: int) -> Context:
    T = investor.months
    if tensor.n_months < T:
        raise ValueError("scenario tensor has %d months, investor needs %d" % (tensor.n_months, T))
    ten = tensor.head(T)
    eq = ten.assets.index("us_eq") if "us_eq" in ten.assets else 0
    lr = np.log1p(ten.real_returns[:, :, eq])
    z = (lr - lr.mean()) / max(lr.std(), 1e-12)
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, 77])))
    labor, pension = simulate_income(ten.n_paths, T, investor.start_age, investor.retirement_age, investor.income,
                                     investor.income_profile, investor.sigma_u, investor.sigma_eps, investor.rho_ye,
                                     z, investor.replacement_rate, investor.pension, rng)
    S = mortality.monthly_survival(q_by_age, investor.start_age, T, investor.mortality)
    beta_m = prefs.beta_annual ** (1.0 / 12.0)
    disc, beq = mortality.discount_weights(S, beta_m)
    if investor.retire_month > 0:
        w_ref = investor.income
    else:
        w_ref = investor.initial_wealth
    return Context(ten, investor, prefs, labor, pension, disc, beq, S, q_by_age, float(w_ref))


def kernel_config(ctx: Context, policy: WeightPolicy, spending: Spending) -> kernel.KernelConfig:
    inv = ctx.investor
    prefs = ctx.prefs
    T = ctx.months
    amort = mortality.amortization_fractions(ctx.q, inv.start_age, T, spending.amort_rate, inv.max_age)
    return kernel.KernelConfig(
        w0=inv.initial_wealth, retire_m=inv.retire_month, spend_rule=kernel.SPEND_CODES[spending.rule],
        rate=spending.withdrawal_rate, savings_rate=inv.savings_rate, wmode=policy.wmode, sched=policy.sched,
        risky_w=policy.risky_w, safe_w=policy.safe_w, theta=policy.theta, bucket_years=policy.bucket_years,
        start_age=inv.start_age, risky_mask=risky_mask(ctx.tensor.assets), rebalance_every=spending.rebalance_months,
        kappa=spending.cost_bps / 10_000.0, disc=ctx.disc, beq=ctx.beq, gamma=prefs.gamma, eta=prefs.eta,
        c_min=prefs.c_min / 12.0, k_shift=prefs.bequest_shift, scale=1000.0, w_ref=ctx.w_ref, amort=amort,
        g_upper=spending.guard_upper, g_lower=spending.guard_lower, g_step=spending.guard_step)


def evaluate(ctx: Context, policy: WeightPolicy, spending: Spending) -> kernel.SimOutput:
    cfg = kernel_config(ctx, policy, spending)
    ten = ctx.tensor
    return kernel.simulate(ten.real_returns, ten.regime, ctx.labor, ctx.pension, cfg)


def ce_annual(out: kernel.SimOutput, gamma: float) -> tuple[float, float]:
    """Annual real CE consumption (dollars) and its Monte Carlo SE."""
    from lifecycle.engine.lifecycle.utility import ce_with_se

    ce, se = ce_with_se(out.utility, gamma, out.sum_disc)
    return ce * 1000.0 * 12.0, se * 1000.0 * 12.0
