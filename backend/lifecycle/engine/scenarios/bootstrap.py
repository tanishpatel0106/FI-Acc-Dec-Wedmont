"""Stationary block bootstrap (Politis-Romano 1994) with Politis-White (2004) block length."""
import math
from typing import Any

import numpy as np
from numpy.typing import NDArray


def _flat_top(t: NDArray[np.float64]) -> NDArray[np.float64]:
    a = np.abs(t)
    return np.where(a <= 0.5, 1.0, np.where(a <= 1.0, 2.0 * (1.0 - a), 0.0))


def politis_white_block_length(x: NDArray[np.float64]) -> float:
    """Optimal mean block length for the stationary bootstrap (Patton-Politis-White 2009 correction)."""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    x = x - x.mean()
    kn = max(5, int(math.ceil(math.sqrt(math.log10(n)))))
    m_max = int(math.ceil(math.sqrt(n))) + kn
    b_max = math.ceil(min(3.0 * math.sqrt(n), n / 3.0))
    c = 2.0
    var = float(np.dot(x, x) / n)
    if var <= 0:
        return 1.0
    acf = np.array([np.dot(x[: n - k], x[k:]) / n / var for k in range(m_max + kn + 1)])
    thresh = c * math.sqrt(math.log10(n) / n)
    m_hat = m_max
    for m in range(1, m_max + 1):
        if np.all(np.abs(acf[m + 1: m + kn + 1]) < thresh):
            m_hat = m
            break
    M = min(2 * m_hat, m_max)
    ks = np.arange(-M, M + 1)
    lam = _flat_top(ks / M) if M > 0 else np.ones(1)
    r = acf[np.abs(ks)] * var
    g = float(np.sum(lam * np.abs(ks) * r))
    g0 = float(np.sum(lam * r))
    d_sb = 2.0 * g0 * g0
    if d_sb <= 0:
        return 1.0
    b = (2.0 * g * g / d_sb) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    return float(min(max(b, 1.0), b_max))


class StationaryBootstrap:
    name = "bootstrap"
    deterministic = False

    def __init__(self, real: NDArray[np.float64], infl: NDArray[np.float64], block_length: float | None = None,
                 labels: NDArray[np.int64] | None = None, n_regimes: int = 1) -> None:
        self.real = real
        self.infl = infl
        self.labels = labels if labels is not None else np.zeros(len(infl), dtype=np.int64)
        self.n_regimes = n_regimes
        if block_length is None:
            # one block length for the joint vector: the average of the per-series choices
            per = [politis_white_block_length(real[:, j]) for j in range(real.shape[1])]
            per.append(politis_white_block_length(infl))
            self.per_series = per
            block_length = float(np.mean(per))
        else:
            self.per_series = []
        self.block_length = float(block_length)

    def simulate(self, n: int, months: int, rng: np.random.Generator,
                 start_regime: int | None) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int64]]:
        T = self.real.shape[0]
        p = 1.0 / self.block_length
        idx = np.empty((n, months), dtype=np.int64)
        if start_regime is not None:
            pool = np.flatnonzero(self.labels == start_regime)
            if len(pool) == 0:
                pool = np.arange(T)
            cur = pool[rng.integers(0, len(pool), n)]
        else:
            cur = rng.integers(0, T, n)
        idx[:, 0] = cur
        for t in range(1, months):
            jump = rng.random(n) < p
            nxt = (cur + 1) % T  # circular wrap keeps every month equally likely
            fresh = rng.integers(0, T, n)
            cur = np.where(jump, fresh, nxt)
            idx[:, t] = cur
        return self.real[idx], self.infl[idx], self.labels[idx]

    def describe(self) -> dict[str, Any]:
        return {"generator": self.name, "mean_block_length": self.block_length,
                "politis_white_per_series": self.per_series, "history_months": int(self.real.shape[0])}
