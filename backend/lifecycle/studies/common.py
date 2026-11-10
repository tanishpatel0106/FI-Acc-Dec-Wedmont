"""Shared building blocks for the v2 research studies.

Every study is a frozen, hashable Pydantic spec executed as a registry job (its run ID is the SHA-256 of
the canonical spec + catalog hash). Studies reuse the engine's scenario tensors (common random numbers)
and the v2 holdings ledger. Only derived statistics are persisted.
"""
from collections.abc import Callable
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from lifecycle.data import panel
from lifecycle.engine.lifecycle import ledger
from lifecycle.engine.lifecycle.simulator import Context
from lifecycle.engine.lifecycle.utility import ce_from_utility, ce_with_se, paired_delta_ce, path_ce
from lifecycle.engine.scenarios.base import ScenarioTensor
from lifecycle.runs import context as C
from lifecycle.runs.spec import ExperimentSpec, Generator, UniverseName

Progress = Callable[[str, float], None]
SCALE = 1000.0 * 12.0


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StudyData(Frozen):
    universe: UniverseName = "core"
    calibration_start: str | None = None
    calibration_end: str | None = None
    catalog_hash: str | None = None


class StudyScenario(Frozen):
    generator: Generator = "bootstrap"
    n_paths: int = Field(2000, ge=100, le=50_000)
    n_train_paths: int = Field(1000, ge=100, le=20_000)
    seed: int = 20261107
    block_length: float | None = Field(None, gt=0)
    k_regimes: int = Field(2, ge=1, le=3)


class StudyInvestor(Frozen):
    age: float = Field(65.0, ge=20, le=90)
    retirement_age: float = Field(65.0, ge=40, le=80)
    horizon_years: int = Field(30, ge=5, le=75)
    initial_wealth: float = Field(1_000_000.0, gt=0)
    income: float = Field(0.0, ge=0)
    pension: float = Field(0.0, ge=0)
    savings_rate: float = Field(0.10, ge=0, le=0.8)
    mortality: bool = True
    sex: Literal["male", "female", "unisex"] = "unisex"


class StudyPrefs(Frozen):
    gamma: float = Field(4.0, ge=0.5, le=15)
    beta_annual: float = Field(0.97, gt=0.5, le=1.0)
    util_floor_annual: float = Field(3000.0, gt=0)   # utility evaluated at max(c, floor); never counted as funded


class StudyCosts(Frozen):
    commission_bps: float = Field(0.0, ge=0, le=100)
    half_spread_bps: float = Field(0.0, ge=0, le=100)
    slippage_bps: float = Field(0.0, ge=0, le=100)


class IncompatibleUniverse(RuntimeError):
    """A universe cannot be materialised (missing entitlement, coverage or series)."""


def experiment_spec(data: StudyData, scen: StudyScenario, inv: StudyInvestor, prefs: StudyPrefs | None = None,
                    seed: int | None = None, generator: str | None = None, n_paths: int | None = None) -> ExperimentSpec:
    """Map study inputs onto the legacy ExperimentSpec so tensors/contexts come from the shared caches."""
    max_age = inv.age + inv.horizon_years
    if max_age > 110:
        raise ValueError("age + horizon exceeds 110")
    pr = prefs or StudyPrefs()
    return ExperimentSpec.model_validate({
        "data": {"universe": data.universe, "calibration_start": data.calibration_start,
                 "calibration_end": data.calibration_end, "catalog_hash": data.catalog_hash},
        "scenario": {"generator": generator or scen.generator, "n_paths": n_paths or scen.n_paths,
                     "n_train_paths": min(scen.n_train_paths, n_paths or scen.n_paths),
                     "seed": scen.seed if seed is None else seed, "block_length": scen.block_length,
                     "k_regimes": scen.k_regimes},
        "investor": {"start_age": inv.age, "retirement_age": min(max(inv.retirement_age, 40.0), 80.0),
                     "max_age": max(max_age, 70.0), "initial_wealth": inv.initial_wealth, "income": inv.income,
                     "income_profile": "cgm_college", "pension": inv.pension, "savings_rate": inv.savings_rate,
                     "sex": inv.sex, "mortality": inv.mortality},
        "preferences": {"gamma": pr.gamma, "beta_annual": pr.beta_annual, "c_min": max(pr.util_floor_annual, 1.0)},
    })


def universe_or_raise(data: StudyData) -> panel.UniverseData:
    try:
        return panel.universe_data(data.universe, data.calibration_start, data.calibration_end)
    except (RuntimeError, KeyError) as exc:
        raise IncompatibleUniverse(str(exc)) from exc


def months(inv: StudyInvestor) -> int:
    return int(inv.horizon_years * 12)


def get_tensor(spec: ExperimentSpec, seed: int | None = None, n_paths: int | None = None,
               start_regime: int | None = None) -> ScenarioTensor:
    ten = C.tensor(spec, seed=seed, n_paths=n_paths, start_regime=start_regime)
    T = int(round((spec.investor.max_age - spec.investor.start_age) * 12))
    return ten.head(min(T, ten.n_months))


def get_context(spec: ExperimentSpec, ten: ScenarioTensor, seed: int) -> Context:
    return C.build(spec, ten, seed)


def train_test(data: StudyData, scen: StudyScenario, inv: StudyInvestor, prefs: StudyPrefs,
               generator: str | None = None) -> tuple[ExperimentSpec, Context, Context]:
    """Reporting context on seed-set B and a disjoint training context on seed-set A."""
    es = experiment_spec(data, scen, inv, prefs, generator=generator)
    ten = get_tensor(es)
    ctx = get_context(es, ten, es.scenario.seed)
    if es.scenario.generator == "historical":
        return es, ctx, ctx
    tseed = C.train_seed(es)
    tten = get_tensor(es, seed=tseed, n_paths=min(scen.n_train_paths, scen.n_paths))
    return es, ctx, get_context(es, tten, tseed)


def trading(mode: str = "calendar", costs: StudyCosts | None = None, **kw: Any) -> ledger.TradingSpec:
    c = costs or StudyCosts()
    return ledger.TradingSpec(mode=mode, commission_bps=c.commission_bps, half_spread_bps=c.half_spread_bps,
                              slippage_bps=c.slippage_bps, **kw)


# named execution policies used across studies (brief 7.2)
STRATEGIES: dict[str, dict[str, Any]] = {
    "none_buyhold": {"mode": "none_buyhold"},
    "calendar_1m": {"mode": "calendar", "cadence_months": 1},
    "calendar_3m": {"mode": "calendar", "cadence_months": 3},
    "calendar_6m": {"mode": "calendar", "cadence_months": 6},
    "calendar_12m": {"mode": "calendar", "cadence_months": 12},
    "absolute_band_5pp": {"mode": "absolute_band", "abs_band": 0.05, "check_months": 1},
    "absolute_band_5pp_edge": {"mode": "absolute_band", "abs_band": 0.05, "check_months": 1, "to_band_edge": True},
    "absolute_band_10pp": {"mode": "absolute_band", "abs_band": 0.10, "check_months": 1},
    "relative_band_20pct": {"mode": "relative_band", "rel_band": 0.20, "check_months": 1},
    "browne_15_35": {"mode": "browne", "check_months": 12, "floor": 0.15, "ceiling": 0.35},
    "browne_15_35_monthly": {"mode": "browne", "check_months": 1, "floor": 0.15, "ceiling": 0.35},
    "cash_flow_targeting": {"mode": "calendar", "cadence_months": 12, "funding": "cash_flow_targeting"},
    "withdraw_overweight_first": {"mode": "calendar", "cadence_months": 12, "funding": "overweight_first"},
    "cash_first_floor": {"mode": "calendar", "cadence_months": 12, "funding": "cash_first", "reserve_years": 2.0},
    "bond_ladder_first": {"mode": "calendar", "cadence_months": 12, "funding": "bond_ladder_first"},
    "volatility_band": {"mode": "risk_band", "risk_threshold": 0.10, "check_months": 1},
    "utility_net_of_cost": {"mode": "utility_net_of_cost", "check_months": 1, "review_months": 12.0},
}

STRATEGY_FAMILY = {"none_buyhold": "none", "calendar_1m": "calendar", "calendar_3m": "calendar",
                   "calendar_6m": "calendar", "calendar_12m": "calendar", "absolute_band_5pp": "band",
                   "absolute_band_5pp_edge": "band", "absolute_band_10pp": "band", "relative_band_20pct": "band",
                   "browne_15_35": "band", "browne_15_35_monthly": "band", "cash_flow_targeting": "cash-flow aware",
                   "withdraw_overweight_first": "cash-flow aware", "cash_first_floor": "cash-flow aware",
                   "bond_ladder_first": "cash-flow aware", "volatility_band": "risk", "utility_net_of_cost": "risk"}


def strategy(name: str, costs: StudyCosts | None = None, **override: Any) -> ledger.TradingSpec:
    if name not in STRATEGIES:
        raise ValueError("unknown trading strategy: " + name)
    kw = dict(STRATEGIES[name])
    kw.update(override)
    mode = kw.pop("mode")
    return trading(mode, costs, **kw)


def hist_cov(u: panel.UniverseData, assets: tuple[str, ...]) -> NDArray[np.float64]:
    """Calibration-window covariance of monthly real returns (train-only information)."""
    return np.cov(u.real[list(assets)].to_numpy(), rowvar=False).reshape(len(assets), len(assets))


def run(ctx: Context, sched: NDArray[np.float64], tr: ledger.TradingSpec, *, spend: str = "fixed_real",
        rate: float = 0.04, q: float = 0.0, w_ref: float | None = None, record: bool = False, trace: int = -1,
        cov: NDArray[np.float64] | None = None, gamma: float | None = None, util_floor: float = 3000.0,
        zero_income: bool = False, defensive: NDArray[np.float64] | None = None,
        tensor: ScenarioTensor | None = None, state: NDArray[np.int64] | None = None) -> ledger.LedgerOutput:
    """Run the holdings ledger. `state` (N, T) overrides the decision regime as the index into the schedule's
    second axis; passing state[j, t] = j with a (T, N, A) schedule gives every path its own target weights."""
    ten = tensor if tensor is not None else ctx.tensor
    assets = ten.assets
    T = ten.n_months
    cash = assets.index("tbill") if "tbill" in assets else -1
    if defensive is None:
        defensive = np.array([1.0 if panel.defensive(a) else 0.0 for a in assets])
    if sched.ndim == 1:
        sched = ledger.constant_schedule(sched, T)
    inv = ctx.investor
    labor = ctx.labor[:, :T]
    pension = ctx.pension[:, :T]
    if zero_income:
        labor = np.zeros_like(labor)
        pension = np.zeros_like(pension)
    if tensor is not None and tensor.n_paths != ctx.labor.shape[0]:
        labor = np.zeros((tensor.n_paths, T))
        pension = np.zeros((tensor.n_paths, T))
    cfg = ledger.LedgerConfig(
        w0=inv.initial_wealth, retire_m=inv.retire_month, spend_mode=ledger.SPEND_MODES[spend], rate=rate,
        savings_rate=inv.savings_rate, sched=sched, trading=tr, disc=ctx.disc[:T], beq=ctx.beq[:T],
        gamma=ctx.prefs.gamma if gamma is None else gamma, w_ref=w_ref if w_ref is not None else inv.initial_wealth,
        q_signed=q, util_floor_monthly=util_floor / 12.0, defensive=defensive, cash_index=cash, cov=cov,
        record_years=record, trace_path=trace)
    dec = ten.decision_regime() if state is None else state
    return ledger.simulate(ten.real_returns, dec, labor, pension, cfg)


def weights_vector(weights: dict[str, float], assets: tuple[str, ...]) -> NDArray[np.float64]:
    w = np.zeros(len(assets))
    for k, v in weights.items():
        if v == 0:
            continue
        if k not in assets:
            raise IncompatibleUniverse("asset '%s' is not in the universe (%s)" % (k, ", ".join(assets)))
        w[assets.index(k)] = float(v)
    s = w.sum()
    if s <= 0 or np.any(w < 0):
        raise ValueError("weights must be long-only with a positive sum")
    return w / s


# --------------------------------------------------------------------------- statistics


def wilson(p: float, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score interval (valid for iid Monte Carlo replicates conditional on the fitted model)."""
    if n <= 0:
        return float("nan"), float("nan")
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return float(max(centre - half, 0.0)), float(min(centre + half, 1.0))


def success(first: NDArray[np.int64], horizon_months: int) -> NDArray[np.bool_]:
    return (first < 0) | (first >= horizon_months)


def success_block(first: NDArray[np.int64], horizon_months: int, iid: bool = True) -> dict[str, Any]:
    s = success(first, horizon_months)
    p = float(s.mean())
    n = int(len(s))
    lo, hi = wilson(p, n) if iid else (float("nan"), float("nan"))
    return {"p": p, "lo": lo, "hi": hi, "n": n, "method": "Wilson score (iid MC)" if iid else
            "not iid (overlapping historical cohorts): no binomial CI"}


def until_death_success(first: NDArray[np.int64], survival: NDArray[np.float64]) -> float:
    """P(no shortfall while alive) = 1 - E[S(tau) 1{tau observed}] under the deterministic survival curve."""
    hit = first >= 0
    s_at = np.where(hit, survival[np.clip(first, 0, len(survival) - 1)], 0.0)
    return float(1.0 - s_at.mean())


def ce_block(out: ledger.LedgerOutput, gamma: float) -> dict[str, float]:
    ce, se = ce_with_se(out.utility, gamma, out.sum_disc)
    return {"ce": ce * SCALE, "se": se * SCALE}


def delta_block(a: ledger.LedgerOutput, b: ledger.LedgerOutput, gamma: float, n_boot: int = 200,
                seed: int = 7) -> dict[str, Any]:
    """Paired Delta_CE = CE_a / CE_b - 1: delta-method SE and a path-pair bootstrap percentile CI."""
    d, se = paired_delta_ce(a.utility, b.utility, gamma, a.sum_disc)
    out: dict[str, Any] = {"delta": d, "se": se, "lo_delta": d - 1.96 * se, "hi_delta": d + 1.96 * se}
    if n_boot > 0 and len(a.utility) > 10:
        rng = np.random.default_rng(seed)
        n = len(a.utility)
        idx = rng.integers(0, n, (n_boot, n))
        ua = a.utility[idx].mean(axis=1)
        ub = b.utility[idx].mean(axis=1)
        ca = np.array([ce_from_utility(x, gamma, a.sum_disc) for x in ua])
        cb = np.array([ce_from_utility(x, gamma, b.sum_disc) for x in ub])
        boots = ca / np.maximum(cb, 1e-300) - 1
        out["lo"], out["hi"] = float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))
    else:
        out["lo"], out["hi"] = out["lo_delta"], out["hi_delta"]
    out["significant"] = bool(out["lo"] > 0 or out["hi"] < 0)
    return out


def paired_success_diff(a: NDArray[np.bool_], b: NDArray[np.bool_]) -> dict[str, float]:
    d = a.astype(float) - b.astype(float)
    n = len(d)
    m = float(d.mean())
    se = float(d.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0
    return {"diff": m, "se": se, "lo": m - 1.96 * se, "hi": m + 1.96 * se}


def cvar(x: NDArray[np.float64], alpha: float = 0.95) -> float:
    if len(x) == 0:
        return float("nan")
    q = np.quantile(x, alpha)
    tail = x[x >= q]
    return float(tail.mean()) if len(tail) else float(q)


def severity_block(out: ledger.LedgerOutput, n_sample: int = 0, seed: int = 3) -> dict[str, Any]:
    un = out.unmet
    fail = un > 1e-6
    share = np.where(out.desired > 0, un / np.maximum(out.desired, 1e-9), 0.0)
    res: dict[str, Any] = {"p_fail": float(fail.mean()), "mean_unconditional": float(un.mean()),
                           "cvar95_unconditional": cvar(un, 0.95), "mean_share_of_desired": float(share.mean()),
                           "units": "real USD of unmet desired portfolio-funded spending, summed over the horizon"}
    if fail.any():
        f = un[fail]
        res.update({"mean_conditional": float(f.mean()), "median_conditional": float(np.median(f)),
                    "quantiles_conditional": np.quantile(f, [0.05, 0.25, 0.5, 0.75, 0.95]).tolist(),
                    "cvar95_conditional": cvar(f, 0.95)})
        if n_sample > 0:
            rng = np.random.default_rng(seed)
            pick = rng.choice(f, size=min(n_sample, len(f)), replace=False)
            res["sample_conditional"] = np.round(pick, 0).tolist()
    return res


def first_shortfall_block(out: ledger.LedgerOutput, retire_m: int, years: int,
                          survival: NDArray[np.float64]) -> dict[str, Any]:
    f = out.first_shortfall
    hit = f >= 0
    yrs = np.where(hit, (f - retire_m) / 12.0, np.inf)
    t = np.arange(1, years + 1)
    cum = [float(np.mean(yrs < k)) for k in t]
    s_at = np.where(hit, survival[np.clip(f, 0, len(survival) - 1)], 0.0)
    cum_alive = [float(np.mean(np.where(yrs < k, s_at, 0.0))) for k in t]
    hist = np.histogram(yrs[hit], bins=np.arange(0, years + 1))[0].tolist() if hit.any() else [0] * years
    return {"years": t.tolist(), "cumulative": cum, "cumulative_alive": cum_alive, "histogram_years": hist,
            "no_failure_share": float(1 - hit.mean()),
            "censoring": "cumulative = financial shortfall by year (fixed horizon); cumulative_alive weights each "
                         "shortfall by the probability the investor is still alive (SSA period table)"}


def fan(arr: NDArray[np.float64], qs: tuple[float, ...] = (0.05, 0.25, 0.5, 0.75, 0.95)) -> dict[str, list[float]]:
    q = np.quantile(arr, qs, axis=0)
    out = {"p%02d" % int(round(qs[i] * 100)): np.round(np.atleast_1d(q[i]), 2).tolist() for i in range(len(qs))}
    out["mean"] = np.round(np.atleast_1d(arr.mean(axis=0)), 2).tolist()
    return out


def path_ces(out: ledger.LedgerOutput, gamma: float, k: int) -> list[float]:
    return np.round(path_ce(out.utility[:k], gamma, out.sum_disc) * SCALE, 2).tolist()


def provenance(assets: tuple[str, ...]) -> dict[str, dict[str, str]]:
    cat = panel.catalog()
    out = {}
    for a in assets:
        rows = cat[cat["series_id"] == a]
        if len(rows):
            r = rows.iloc[0]
            out[a] = {"provenance": str(r["provenance"]), "source": str(r["source"]),
                      "licence_class": str(r["licence_class"]), "first_obs": str(r["first_obs"]),
                      "last_obs": str(r["last_obs"])}
        else:
            out[a] = {"provenance": "unknown", "source": "unknown", "licence_class": "unknown"}
    return out


def universe_block(u: panel.UniverseData) -> dict[str, Any]:
    prov = provenance(u.assets)
    return {"name": u.name, "assets": list(u.assets), "window": [u.start.date().isoformat(), u.end.date().isoformat()],
            "n_months": int(len(u.real)), "excluded": u.excluded, "dropped_months": u.n_dropped_months,
            "provenance": prov, "data_class": "model_generated" if any(
                v["provenance"] == "model_generated" for v in prov.values()) else "observed"}


def common_warnings(u: panel.UniverseData, ten: ScenarioTensor) -> list[str]:
    w = []
    if any(v["provenance"] == "model_generated" for v in provenance(u.assets).values()):
        w.append("model_generated: some return series are repriced from public yields (not observed total returns)")
    if panel.synthetic_mode():
        w.append("SYNTHETIC DATA: test fixtures only - not research output")
    if ten.meta.get("generator") == "historical":
        w.append("historical cohorts overlap and are not independent; binomial CIs are not reported")
    T = ten.n_months
    if T > len(u.real):
        w.append("simulated horizon (%d months) exceeds the calibration history (%d months): long-horizon results "
                 "extrapolate the fitted model" % (T, len(u.real)))
    return w


def scenario_block(ten: ScenarioTensor) -> dict[str, Any]:
    keep = {k: v for k, v in ten.meta.items() if k in ("generator", "seed", "n_paths", "months", "window",
                                                         "decision_signal", "model")}
    return keep


def ce_of(out: ledger.LedgerOutput, gamma: float) -> float:
    return ce_with_se(out.utility, gamma, out.sum_disc)[0] * SCALE


def resources_ce(term: NDArray[np.float64], funded: NDArray[np.float64], gamma: float,
                 floor: float = 1000.0) -> float:
    """CRRA certainty equivalent of total real resources delivered (terminal wealth + funded draws)."""
    r = np.maximum(term + funded, floor) / 1e6
    if gamma == 1.0:
        return float(np.exp(np.mean(np.log(r))) * 1e6)
    return float(np.mean(r ** (1 - gamma)) ** (1 / (1 - gamma)) * 1e6)


def evidence_grade(n_paths: int, significant: bool | None, robust_checks: int, failed: bool = False) -> str:
    if failed:
        return "invalid"
    if n_paths < 1000:
        return "diagnostic"
    if robust_checks >= 2 and significant:
        return "robust"
    return "conditional"


def to_list(a: Any, digits: int = 6) -> Any:
    arr = np.asarray(a, dtype=float)
    return np.where(np.isfinite(arr), np.round(arr, digits), np.nan).tolist()
