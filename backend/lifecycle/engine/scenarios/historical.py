"""Historical cohorts: rolling start months over the actual joint history (no model risk)."""
from typing import Any

import numpy as np
from numpy.typing import NDArray


class HistoricalCohorts:
    name = "historical"
    deterministic = True

    def __init__(self, real: NDArray[np.float64], infl: NDArray[np.float64], dates: list[str],
                 labels: NDArray[np.int64] | None = None, n_regimes: int = 1, step: int = 1) -> None:
        self.real = real
        self.infl = infl
        self.dates = dates
        self.labels = labels if labels is not None else np.zeros(len(infl), dtype=np.int64)
        self.n_regimes = n_regimes
        self.step = step
        self.last_starts: list[str] = []

    def simulate(self, n: int, months: int, rng: np.random.Generator,
                 start_regime: int | None) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int64]]:
        T = self.real.shape[0]
        if months > T:
            raise ValueError("horizon of %d months exceeds the %d-month history" % (months, T))
        starts = np.arange(0, T - months + 1, self.step)
        if start_regime is not None:
            starts = starts[self.labels[starts] == start_regime]
        self.last_starts = [self.dates[s] for s in starts]
        idx = starts[:, None] + np.arange(months)[None, :]
        return self.real[idx], self.infl[idx], self.labels[idx]

    def describe(self) -> dict[str, Any]:
        return {"generator": self.name, "history_months": int(self.real.shape[0]),
                "first_month": self.dates[0], "last_month": self.dates[-1],
                "caveat": "overlapping cohorts are not independent"}
