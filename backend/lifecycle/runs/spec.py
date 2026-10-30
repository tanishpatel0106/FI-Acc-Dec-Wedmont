"""Frozen, hashable experiment specification (brief 7.3). Its canonical-JSON SHA-256 is the run ID."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Generator = Literal["historical", "bootstrap", "student_t", "markov_switching", "curve_factor"]
PolicyType = Literal["constant_mix", "sixty_forty", "target_date", "glidepath", "risk_parity", "min_variance",
                     "mean_variance", "mean_cvar", "utility_static", "best_constant", "regime", "bucket",
                     "parametric", "dp"]
SpendingRule = Literal["fixed_real", "fixed_pct", "guardrails", "bucket", "utility_optimal"]
Benchmark = Literal["sixty_forty", "target_date", "best_constant", "none"]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DataSpec(Frozen):
    universe: Literal["core", "modern"] = "core"
    calibration_start: str | None = None
    calibration_end: str | None = None
    catalog_hash: str | None = None


class ScenarioSpec(Frozen):
    generator: Generator = "bootstrap"
    n_paths: int = Field(2000, ge=100, le=100_000)
    n_train_paths: int = Field(1000, ge=100, le=20_000)
    horizon_months: int | None = Field(None, ge=12, le=1200)
    seed: int = 20261030
    block_length: float | None = Field(None, gt=0)
    k_regimes: int = Field(2, ge=1, le=3)
    start_regime: int | None = None
    nu: float | None = Field(None, gt=2)


class InvestorSpec(Frozen):
    start_age: float = Field(65.0, ge=20, le=95)
    retirement_age: float = Field(65.0, ge=40, le=80)
    max_age: float = Field(100.0, ge=70, le=110)
    initial_wealth: float = Field(1_000_000.0, ge=0)
    income: float = Field(100_000.0, ge=0)
    income_profile: Literal["flat", "cgm_college", "cgm_highschool"] = "cgm_college"
    sigma_u: float = Field(0.10, ge=0, le=0.5)
    sigma_eps: float = Field(0.10, ge=0, le=0.5)
    rho_ye: float = Field(0.0, ge=-1, le=1)
    replacement_rate: float = Field(0.40, ge=0, le=1.5)
    pension: float | None = Field(20_000.0, ge=0)
    savings_rate: float = Field(0.10, ge=0, le=0.8)
    sex: Literal["male", "female", "unisex"] = "unisex"
    mortality: bool = True


class PreferencesSpec(Frozen):
    gamma: float = Field(4.0, ge=0.5, le=15)
    beta_annual: float = Field(0.97, gt=0.5, le=1.0)
    eta: float = Field(0.0, ge=0)
    c_min: float = Field(6_000.0, gt=0)
    bequest_shift: float = Field(10_000.0, gt=0)


class PolicySpec(Frozen):
    type: PolicyType = "sixty_forty"
    weights: dict[str, float] | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    spending_rule: SpendingRule = "fixed_real"
    withdrawal_rate: float = Field(0.04, ge=0, le=0.2)
    rebalance_months: int = Field(1, ge=1, le=60)
    cost_bps: float = Field(0.0, ge=0, le=200)


class OutputsSpec(Frozen):
    benchmark: Benchmark = "sixty_forty"
    quantiles: tuple[float, ...] = (0.05, 0.25, 0.5, 0.75, 0.95)
    persist_paths: bool = False
    n_sample_paths: int = Field(150, ge=0, le=2000)


class ExperimentSpec(Frozen):
    data: DataSpec = Field(default_factory=DataSpec)
    scenario: ScenarioSpec = Field(default_factory=ScenarioSpec)
    investor: InvestorSpec = Field(default_factory=InvestorSpec)
    preferences: PreferencesSpec = Field(default_factory=PreferencesSpec)
    policy: PolicySpec = Field(default_factory=PolicySpec)
    outputs: OutputsSpec = Field(default_factory=OutputsSpec)


class SweepSpec(Frozen):
    base: ExperimentSpec = Field(default_factory=ExperimentSpec)
    kind: Literal["decumulation", "accumulation"] = "decumulation"
    withdrawal_rates: tuple[float, ...] = tuple(round(0.02 + 0.005 * i, 4) for i in range(13))
    years_relative: tuple[float, ...] = (-20, -15, -10, -5, 0, 5, 10)
    savings_rates: tuple[float, ...] = (0.05, 0.10, 0.15, 0.20)
    start_ages: tuple[float, ...] = (30, 40, 50)
    optimizer: Literal["parametric", "glidepath", "best_constant", "utility_static"] = "parametric"
    benchmarks: tuple[Benchmark, ...] = ("sixty_forty", "target_date", "best_constant")
    label: str | None = None


class CompareSpec(Frozen):
    run_ids: tuple[str, ...]
    n_divergent: int = 50


class ValidationSpec(Frozen):
    run_id: str
    path_counts: tuple[int, ...] = (1000, 2500, 5000, 10000)
    n_param_boot: int = Field(20, ge=0, le=500)
    generators: tuple[Generator, ...] = ("bootstrap", "student_t", "markov_switching")
    cohort_years: float = 30.0


class AttributionSpec(Frozen):
    sweep_id: str
    universe: Literal["core", "modern"] = "modern"
    base: tuple[str, ...] = ("us_eq", "ust_10y")
    sleeves: tuple[str, ...] | None = None
    by_regime: bool = True
    n_paths: int = 1000
