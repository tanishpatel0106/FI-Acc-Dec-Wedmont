"""Construct a fitted generator by name from historical arrays."""
from typing import Any

import numpy as np
from numpy.typing import NDArray

from lifecycle.engine.scenarios.bootstrap import StationaryBootstrap
from lifecycle.engine.scenarios.curve_factors import CurveFactorModel
from lifecycle.engine.scenarios.historical import HistoricalCohorts
from lifecycle.engine.scenarios.markov_switching import MarkovSwitching
from lifecycle.engine.scenarios.student_t import MultivariateT

GENERATORS = ("historical", "bootstrap", "student_t", "markov_switching", "curve_factor")


def fit_generator(name: str, real: NDArray[np.float64], infl: NDArray[np.float64], assets: tuple[str, ...],
                  dates: list[str], params: dict[str, Any], labels: NDArray[np.int64] | None = None,
                  n_label_regimes: int = 1, yields: NDArray[np.float64] | None = None,
                  maturities: list[float] | None = None) -> Any:
    if name == "historical":
        return HistoricalCohorts(real, infl, dates, labels, n_label_regimes, step=int(params.get("step", 1)))
    if name == "bootstrap":
        return StationaryBootstrap(real, infl, params.get("block_length"), labels, n_label_regimes)
    if name == "student_t":
        return MultivariateT(real, infl, params.get("nu"))
    if name == "markov_switching":
        return MarkovSwitching(real, infl, k=int(params.get("k_regimes", 2)))
    if name == "curve_factor":
        if yields is None or maturities is None:
            raise ValueError("curve_factor generator needs the GSW yield panel")
        return CurveFactorModel(real, infl, assets, yields, maturities)
    raise ValueError("unknown generator: " + name)
