"""Respect recorded publication lags in retrospective historical calibration."""
import pandas as pd

from lifecycle.data import panel
from lifecycle.data.series import UNIVERSES


def known_history_end(universe, proposed_end, decision_date):
    definition = UNIVERSES[universe]
    ids = [*definition.required, definition.inflation]
    deadline = pd.Timestamp(decision_date)
    p = panel.panel()
    eligible = p[p.series_id.isin(ids) & (p.month_end <= pd.Timestamp(proposed_end))
                 & (p.available_from < deadline)]
    latest = eligible.groupby('series_id').month_end.max()
    if set(latest.index) != set(ids):
        raise ValueError('Required inputs are unavailable before the portfolio decision')
    cutoff = latest.min()
    included = p[p.series_id.isin(ids) & (p.month_end <= cutoff)]
    if not (included.available_from < deadline).all():
        raise ValueError('A training observation is not yet published at the decision date')
    return cutoff.date().isoformat(), included.available_from.max().date().isoformat()
