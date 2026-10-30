"""Standard scenario tensor and chunked, worker-count-invariant generation."""
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

CHUNK = 2000  # paths per chunk; each chunk gets its own SeedSequence child


@dataclass
class ScenarioTensor:
    assets: tuple[str, ...]
    real_returns: NDArray[np.float64]   # (N, T, A) real simple returns
    inflation: NDArray[np.float64]      # (N, T) CPI inflation
    regime: NDArray[np.int64]           # (N, T) regime label, 0 when the generator has none
    n_regimes: int
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def n_paths(self) -> int:
        return int(self.real_returns.shape[0])

    @property
    def n_months(self) -> int:
        return int(self.real_returns.shape[1])

    def head(self, months: int) -> "ScenarioTensor":
        if months > self.n_months:
            raise ValueError("requested %d months from a %d-month tensor" % (months, self.n_months))
        return ScenarioTensor(self.assets, self.real_returns[:, :months], self.inflation[:, :months],
                              self.regime[:, :months], self.n_regimes, dict(self.meta))

    def subset_paths(self, idx: NDArray[np.int64]) -> "ScenarioTensor":
        return ScenarioTensor(self.assets, self.real_returns[idx], self.inflation[idx], self.regime[idx],
                              self.n_regimes, dict(self.meta))

    def select_assets(self, assets: list[str]) -> "ScenarioTensor":
        cols = [self.assets.index(a) for a in assets]
        return ScenarioTensor(tuple(assets), self.real_returns[:, :, cols], self.inflation, self.regime,
                              self.n_regimes, dict(self.meta))

    def nominal_returns(self) -> NDArray[np.float64]:
        return (1.0 + self.real_returns) * (1.0 + self.inflation[:, :, None]) - 1.0


class FittedGenerator(Protocol):
    name: str
    n_regimes: int
    deterministic: bool

    def simulate(self, n: int, months: int, rng: np.random.Generator,
                 start_regime: int | None) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int64]]:
        ...

    def describe(self) -> dict[str, Any]:
        ...


def generate(model: FittedGenerator, assets: tuple[str, ...], n_paths: int, months: int, seed: int,
             start_regime: int | None = None) -> ScenarioTensor:
    """Generate in fixed-size chunks with SeedSequence.spawn so results do not depend on worker count."""
    if model.deterministic:
        real, infl, reg = model.simulate(n_paths, months, np.random.default_rng(seed), start_regime)
    else:
        n_chunks = (n_paths + CHUNK - 1) // CHUNK
        children = np.random.SeedSequence(seed).spawn(n_chunks)
        parts_r, parts_i, parts_g = [], [], []
        for c in range(n_chunks):
            size = min(CHUNK, n_paths - c * CHUNK)
            rng = np.random.Generator(np.random.PCG64(children[c]))
            r, i, g = model.simulate(size, months, rng, start_regime)
            parts_r.append(r)
            parts_i.append(i)
            parts_g.append(g)
        real = np.concatenate(parts_r, axis=0)
        infl = np.concatenate(parts_i, axis=0)
        reg = np.concatenate(parts_g, axis=0)
    return ScenarioTensor(assets, np.ascontiguousarray(real, dtype=np.float64),
                          np.ascontiguousarray(infl, dtype=np.float64),
                          np.ascontiguousarray(reg, dtype=np.int64), model.n_regimes,
                          {"generator": model.name, "seed": seed, "n_paths": int(real.shape[0]), "months": months})


def to_features(real: NDArray[np.float64], infl: NDArray[np.float64]) -> NDArray[np.float64]:
    """Joint modelling space: log gross real returns of every asset plus CPI inflation."""
    return np.column_stack([np.log1p(real), infl])


def from_features(x: NDArray[np.float64], n_assets: int) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    real = np.expm1(x[..., :n_assets])
    infl = x[..., n_assets]
    return real, infl
