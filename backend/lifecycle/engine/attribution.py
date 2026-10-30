"""M6 attribution: marginal asset-class utility, Shapley values over sleeves, sequence-risk isolation."""
from collections.abc import Callable
from itertools import combinations
from math import factorial
from typing import Any

import numpy as np
from numpy.typing import NDArray


def marginal_utility(base: tuple[str, ...], sleeves: tuple[str, ...],
                     ce_star: Callable[[tuple[str, ...]], float]) -> dict[str, float]:
    """MU_k = CE*(A u {k}) - CE*(A) with A the base universe."""
    base_ce = ce_star(base)
    out = {}
    for k in sleeves:
        out[k] = ce_star(tuple(base) + (k,)) - base_ce
    return out


def shapley(base: tuple[str, ...], sleeves: tuple[str, ...],
            ce_star: Callable[[tuple[str, ...]], float]) -> tuple[dict[str, float], dict[tuple[str, ...], float]]:
    """Exact Shapley decomposition of CE*(base u all sleeves) - CE*(base) over sleeves."""
    n = len(sleeves)
    values: dict[tuple[str, ...], float] = {}
    for r in range(n + 1):
        for combo in combinations(sleeves, r):
            key = tuple(sorted(combo))
            values[key] = ce_star(tuple(base) + key)
    phi = {}
    for k in sleeves:
        others = [s for s in sleeves if s != k]
        total = 0.0
        for r in range(len(others) + 1):
            weight = factorial(r) * factorial(n - r - 1) / factorial(n)
            for combo in combinations(others, r):
                s = tuple(sorted(combo))
                with_k = tuple(sorted(combo + (k,)))
                total += weight * (values[with_k] - values[s])
        phi[k] = total
    return phi, values


def sequence_risk(window_real: NDArray[np.float64], outcome: Callable[[NDArray[np.float64]], float],
                  n_perm: int = 500, seed: int = 0) -> dict[str, Any]:
    """Permute the order of jointly observed monthly vectors (values held fixed): a controlled timing
    counterfactual, not a forecast."""
    rng = np.random.default_rng(seed)
    actual = outcome(window_real)
    perms = np.empty(n_perm)
    for i in range(n_perm):
        perms[i] = outcome(window_real[rng.permutation(window_real.shape[0])])
    return {"actual": float(actual), "permuted_mean": float(perms.mean()),
            "permuted_quantiles": np.quantile(perms, [0.05, 0.25, 0.5, 0.75, 0.95]).tolist(),
            "percentile_of_actual": float(np.mean(perms <= actual)), "timing_effect": float(actual - perms.mean()),
            "permuted": perms.tolist()}
