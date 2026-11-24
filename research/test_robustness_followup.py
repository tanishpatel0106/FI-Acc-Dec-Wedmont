"""Analytical conservation and validation-separation checks for the extension."""
import numpy as np
import pandas as pd

from lifecycle.engine.scenarios import ScenarioTensor
from robustness_followup import ce, fit_policies, grid
from calibration_cutoff import known_history_end


def test_resource_ce_of_deterministic_values_matches_the_values():
    values = np.array([100., 10000., 1000000.])[:, None]*np.ones((3, 20))
    for gamma in [1, 2, 4, 8]:
        assert np.allclose(ce(values, gamma, floor=100), values[:, 0])
        assert np.allclose(ce(values*1.1, gamma, floor=100)/ce(values, gamma, floor=100)-1, .1)


def test_validation_can_reject_conditional_fitting_noise():
    train = np.empty((2, 2, 3, 100))
    train[:, 0, :, :50] = np.array([110., 100., 80.])[None, :, None]
    train[:, 1, :, :50] = np.array([80., 100., 110.])[None, :, None]
    train[..., 50:] = np.array([80., 100., 80.])[None, None, :, None]
    policies, alpha = fit_policies(train, np.array([0., .5, 1.]), np.array([.5, .5]), floor=1)
    assert alpha == 0
    assert np.array_equal(policies['validated_shrinkage'], policies['horizon_only'])


def test_resource_grid_conserves_money_without_returns_or_costs():
    assets = ('us_eq', 'tbill', 'ust_10y')
    ten = ScenarioTensor(assets, np.zeros((4, 120, 3)), np.zeros((4, 120)),
                         np.zeros((4, 120), dtype=np.int64), 1)
    outputs = grid(ten, '1953-01-01', '2024-12-31', 3, [10], np.array([-.02, .04, .2]), np.array([.4]))
    assert np.allclose(outputs['resources'][0, :, 0], np.array([1200000., 1000000., 1000000.])[:, None])
    assert np.allclose(outputs['terminal'][0, :, 0], np.array([1200000., 600000., 0.])[:, None])
    assert np.allclose(outputs['unmet'][0, 2, 0], 1000000.)
    assert outputs['success'][0, 0, 0].all() and outputs['success'][0, 1, 0].all()
    assert not outputs['success'][0, 2, 0].any()


def test_january_decision_excludes_unpublished_december_cpi(monkeypatch):
    from lifecycle.data import panel

    dates = pd.to_datetime(['1999-11-30', '1999-12-31'])
    rows = []
    for sid in ['us_eq', 'tbill', 'ust_10y', 'cpi_nsa']:
        for date in dates:
            rows.append(dict(series_id=sid, month_end=date,
                available_from=date+pd.Timedelta(days=15 if sid=='cpi_nsa' else 0)))
    monkeypatch.setattr(panel, 'panel', lambda: pd.DataFrame(rows))
    cutoff, latest = known_history_end('core_long_history', '1999-12-31', '2000-01-01')
    assert cutoff == '1999-11-30'
    assert latest == '1999-12-15'
