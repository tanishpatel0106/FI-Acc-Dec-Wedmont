import numpy as np

from lifecycle import ENGINE_SEMANTIC_VERSION
from lifecycle.runs import hashing
from lifecycle.studies import common as S
from lifecycle.studies.frontier import _surface
from lifecycle.studies.signed_flow import paired_resources_comparison


def test_young_investor_horizon_is_not_extended_to_age_70():
    investor = S.StudyInvestor(age=35, retirement_age=65, horizon_years=10)
    spec = S.experiment_spec(S.StudyData(universe="core_long_history"),
                             S.StudyScenario(n_paths=100, n_train_paths=100), investor)
    assert spec.investor.max_age == 45
    assert S.get_tensor(spec).n_months == 120


def test_shortfall_cvar_handles_a_large_atom_at_zero():
    losses = np.r_[np.zeros(990), np.ones(10)]
    assert np.isclose(S.cvar(losses, 0.95), 0.2)


def test_dated_studies_change_identity_when_the_data_change(monkeypatch):
    from lifecycle.data import panel
    from lifecycle.runs import executor
    from lifecycle.studies.historical_replay import HistoricalReplaySpec
    from lifecycle.studies.lifecycle_sim import LifecycleSimSpec

    for kind, spec in (("historical_replay", HistoricalReplaySpec()), ("lifecycle_sim", LifecycleSimSpec())):
        monkeypatch.setattr(panel, "catalog_hash", lambda: "first-vintage")
        before = hashing.run_id_for(kind, executor.with_catalog(spec))
        monkeypatch.setattr(panel, "catalog_hash", lambda: "second-vintage")
        after = hashing.run_id_for(kind, executor.with_catalog(spec))
        assert before != after


def test_frontier_welfare_uses_the_selected_success_horizon():
    investor = S.StudyInvestor(horizon_years=40)
    spec = S.experiment_spec(S.StudyData(universe="core_long_history"),
                             S.StudyScenario(n_paths=100, n_train_paths=100), investor)
    tensor = S.get_tensor(spec)
    context = S.get_context(spec, tensor, spec.scenario.seed)
    trading = S.strategy("calendar_12m")
    result = _surface(context, tensor.assets, "us_eq", "ust_10y", [0.04], [0.4], trading,
                      (30, 40), True, 3000, ce_horizon=30)
    weights = S.weights_vector({"us_eq": 0.6, "ust_10y": 0.4}, tensor.assets)
    direct = S.run(context, weights, trading, rate=0.04, tensor=tensor.head(360))
    assert np.isclose(result[1][0, 0], S.ce_of(direct, 4))
    assert np.isclose(result[0][0, 0, 0], S.success(direct.first_shortfall, 360).mean())


def test_paired_resource_interval_keeps_common_paths_together():
    values = np.random.default_rng(2).lognormal(13, 0.8, (4, 150))
    identical = paired_resources_comparison(values, values, 4, n_boot=30)
    assert identical["delta"] == identical["lo"] == identical["hi"] == 0
    scaled = paired_resources_comparison(values * 1.1, values, 4, n_boot=30)
    assert np.allclose([scaled["delta"], scaled["lo"], scaled["hi"]], 0.1)


def test_engine_correction_changes_run_identity(monkeypatch):
    import lifecycle

    current = hashing.run_id_for("frontier", {"same": "inputs"})
    monkeypatch.setattr(lifecycle, "ENGINE_SEMANTIC_VERSION", ENGINE_SEMANTIC_VERSION + ".previous")
    assert hashing.run_id_for("frontier", {"same": "inputs"}) != current
