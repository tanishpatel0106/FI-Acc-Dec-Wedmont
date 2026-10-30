"""Map an ExperimentSpec onto engine objects, with in-memory caches for fitted models and tensors.

Tensors are keyed by (data, scenario, months) so every policy and benchmark in a run, and every
cell of a sweep, is evaluated on identical paths (common random numbers).
"""
import threading
from collections import OrderedDict
from typing import Any

import numpy as np

from lifecycle.data import panel
from lifecycle.data.ingest_ssa import load_life_table
from lifecycle.engine.lifecycle import mortality
from lifecycle.engine.lifecycle.simulator import Context, Investor, Preferences, Spending, build_context
from lifecycle.engine.scenarios import ScenarioTensor, fit_generator, generate
from lifecycle.engine.scenarios.markov_switching import MarkovSwitching
from lifecycle.runs.hashing import canonical_json, sha256_hex
from lifecycle.runs.spec import ExperimentSpec

_LOCK = threading.RLock()
_MODELS: "OrderedDict[str, Any]" = OrderedDict()
_TENSORS: "OrderedDict[str, ScenarioTensor]" = OrderedDict()
MAX_MODELS = 24
MAX_TENSORS = 6

GSW_MATURITIES = [1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0]


def _put(cache: OrderedDict, key: str, value: Any, cap: int) -> None:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > cap:
        cache.popitem(last=False)


def universe(spec: ExperimentSpec) -> panel.UniverseData:
    return panel.universe_data(spec.data.universe, spec.data.calibration_start, spec.data.calibration_end)


def history_labels(u: panel.UniverseData, k: int) -> tuple[np.ndarray, int, Any]:
    """Filtered MS regime labels on history (point-in-time argmax), used by non-MS generators."""
    key = "labels:" + u.name + ":" + str(u.start) + ":" + str(u.end) + ":" + str(k) + ":" + u.catalog_hash
    with _LOCK:
        if key in _MODELS:
            return _MODELS[key]
    ms = MarkovSwitching(u.real_array(), u.inflation.to_numpy(), k=k)
    out = (ms.labels, k, ms)
    with _LOCK:
        _put(_MODELS, key, out, MAX_MODELS)
    return out


def _yield_panel(u: panel.UniverseData) -> tuple[np.ndarray | None, list[float], panel.UniverseData]:
    ids = ["gsw_nom_%02d" % int(m) for m in GSW_MATURITIES]
    wide = panel.wide(ids)
    needed_max = 10.0
    for a in u.assets:
        if a == "ust_20y":
            needed_max = max(needed_max, 20.0)
        if a == "ust_30y":
            needed_max = max(needed_max, 30.0)
    mats = [m for m in GSW_MATURITIES if m <= needed_max]
    wide = wide[["gsw_nom_%02d" % int(m) for m in mats]].dropna()
    common = u.real.index.intersection(wide.index)
    return wide.loc[common].to_numpy(), mats, u


def fitted_model(spec: ExperimentSpec, u: panel.UniverseData | None = None) -> Any:
    if u is None:
        u = universe(spec)
    sc = spec.scenario
    key = sha256_hex(canonical_json({"data": spec.data.model_dump(mode="json"), "g": sc.generator,
                                     "b": sc.block_length, "k": sc.k_regimes, "nu": sc.nu, "cat": u.catalog_hash}))
    with _LOCK:
        if key in _MODELS:
            _MODELS.move_to_end(key)
            return _MODELS[key]
    real = u.real_array()
    infl = u.inflation.to_numpy()
    dates = [d.date().isoformat() for d in u.real.index]
    labels = None
    n_lab = 1
    if sc.generator in ("historical", "bootstrap") and sc.k_regimes > 1:
        labels, n_lab, _ = history_labels(u, sc.k_regimes)
    params = {"block_length": sc.block_length, "k_regimes": sc.k_regimes, "nu": sc.nu}
    if sc.generator == "curve_factor":
        ylds, mats, _ = _yield_panel(u)
        common = u.real.index.intersection(panel.wide(["gsw_nom_%02d" % int(m) for m in mats]).dropna().index)
        mask = u.real.index.isin(common)
        model = fit_generator("curve_factor", real[mask], infl[mask], u.assets, dates, params, yields=ylds,
                              maturities=mats)
    else:
        model = fit_generator(sc.generator, real, infl, u.assets, dates, params, labels, n_lab)
    with _LOCK:
        _put(_MODELS, key, model, MAX_MODELS)
    return model


def horizon(spec: ExperimentSpec) -> int:
    T = int(round((spec.investor.max_age - spec.investor.start_age) * 12))
    if spec.scenario.horizon_months is not None:
        if spec.scenario.horizon_months < T:
            raise ValueError("scenario.horizon_months is shorter than the investor horizon (%d months)" % T)
        return int(spec.scenario.horizon_months)
    return T


def tensor(spec: ExperimentSpec, seed: int | None = None, n_paths: int | None = None,
           start_regime: int | None = None) -> ScenarioTensor:
    sc = spec.scenario
    seed = sc.seed if seed is None else seed
    n = sc.n_paths if n_paths is None else n_paths
    months = horizon(spec)
    sr = sc.start_regime if start_regime is None else start_regime
    key = sha256_hex(canonical_json({"data": spec.data.model_dump(mode="json"), "sc": sc.model_dump(mode="json"),
                                     "seed": seed, "n": n, "T": months, "sr": sr}))
    with _LOCK:
        if key in _TENSORS:
            _TENSORS.move_to_end(key)
            return _TENSORS[key]
    u = universe(spec)
    model = fitted_model(spec, u)
    ten = generate(model, u.assets, n, months, seed, sr)
    ten.meta["model"] = model.describe()
    ten.meta["window"] = [u.start.date().isoformat(), u.end.date().isoformat()]
    if hasattr(model, "last_starts"):
        ten.meta["cohort_starts"] = list(model.last_starts)
    with _LOCK:
        _put(_TENSORS, key, ten, MAX_TENSORS)
    return ten


def train_seed(spec: ExperimentSpec) -> int:
    """Seed-set A (policy fitting) is derived from, and disjoint from, seed-set B (reporting)."""
    return int(np.random.SeedSequence([spec.scenario.seed, 1]).generate_state(1)[0])


def investor(spec: ExperimentSpec) -> Investor:
    i = spec.investor
    return Investor(start_age=i.start_age, retirement_age=i.retirement_age, max_age=i.max_age,
                    initial_wealth=i.initial_wealth, income=i.income, income_profile=i.income_profile,
                    sigma_u=i.sigma_u, sigma_eps=i.sigma_eps, rho_ye=i.rho_ye, replacement_rate=i.replacement_rate,
                    pension=i.pension, savings_rate=i.savings_rate, sex=i.sex, mortality=i.mortality)


def preferences(spec: ExperimentSpec) -> Preferences:
    p = spec.preferences
    return Preferences(gamma=p.gamma, beta_annual=p.beta_annual, eta=p.eta, c_min=p.c_min,
                       bequest_shift=p.bequest_shift)


def spending(spec: ExperimentSpec) -> Spending:
    p = spec.policy
    rule = p.spending_rule
    if rule == "bucket":
        rule = "fixed_real"
    amort = float(p.params.get("amort_rate", 0.02)) if isinstance(p.params, dict) else 0.02
    return Spending(rule=rule, withdrawal_rate=p.withdrawal_rate, amort_rate=amort,
                    rebalance_months=p.rebalance_months, cost_bps=p.cost_bps)


def benchmark_spending(spec: ExperimentSpec) -> Spending:
    """Benchmarks always spend by the fixed-real rule at the same withdrawal rate, rebalancing and cost."""
    p = spec.policy
    return Spending(rule="fixed_real", withdrawal_rate=p.withdrawal_rate, rebalance_months=p.rebalance_months,
                    cost_bps=p.cost_bps)


def q_vector(spec: ExperimentSpec) -> np.ndarray:
    return mortality.q_vector(load_life_table(), spec.investor.sex)


def life_table_provenance() -> str:
    t = load_life_table()
    return str(t["source"].iloc[0]) if "source" in t.columns else "unknown"


def build(spec: ExperimentSpec, ten: ScenarioTensor, seed: int) -> Context:
    return build_context(ten, investor(spec), preferences(spec), q_vector(spec), seed)
