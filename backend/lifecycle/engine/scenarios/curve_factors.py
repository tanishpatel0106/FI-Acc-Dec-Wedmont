"""Yield-curve-factor scenario model (R3).

Simulates level/slope/curvature scores jointly with inflation and non-bond log real
returns (VAR(1), residual bootstrap), rebuilds the curve and derives Treasury returns
from carry plus repricing, so bond returns are consistent with simulated rates.
"""
from typing import Any

import numpy as np
from numpy.typing import NDArray

BOND_MATURITY = {"ust_2y": 2.0, "ust_5y": 5.0, "ust_10y": 10.0, "ust_20y": 20.0, "ust_30y": 30.0}


def par_bond_return_vec(y0: NDArray[np.float64], y1: NDArray[np.float64], maturity: float,
                        freq: int = 2) -> NDArray[np.float64]:
    n = maturity * freq - freq / 12.0
    whole = int(np.floor(n + 1e-12))
    frac = n - whole
    if frac > 1e-9:
        times = frac + np.arange(whole + 1, dtype=float)
    else:
        times = np.arange(1, whole + 1, dtype=float)
    disc = (1.0 + y1[..., None] / freq) ** (-times)
    return (y0 / freq) * disc.sum(axis=-1) + disc[..., -1] - 1.0


class CurveFactorModel:
    name = "curve_factor"
    deterministic = False
    n_regimes = 1

    def __init__(self, real: NDArray[np.float64], infl: NDArray[np.float64], assets: tuple[str, ...],
                 yields: NDArray[np.float64], maturities: list[float], n_factors: int = 3) -> None:
        self.assets = assets
        self.maturities = np.asarray(maturities, dtype=float)
        self.bond_idx = [i for i, a in enumerate(assets) if a in BOND_MATURITY]
        self.direct_idx = [i for i, a in enumerate(assets) if a not in BOND_MATURITY]
        self.mean_y = yields.mean(axis=0)
        centered = yields - self.mean_y
        cov = np.cov(centered, rowvar=False)
        evals, evecs = np.linalg.eigh(cov)
        order = np.argsort(evals)[::-1][:n_factors]
        self.loadings = evecs[:, order]
        # sign convention: level loads positively on average, slope rises with maturity
        for k in range(n_factors):
            ref = self.loadings[:, k].mean() if k == 0 else self.loadings[-1, k] - self.loadings[0, k]
            if ref < 0:
                self.loadings[:, k] *= -1
        self.explained = (evals[order] / evals.sum()).tolist()
        scores = centered @ self.loadings
        z = np.column_stack([scores, infl, np.log1p(real[:, self.direct_idx])])
        X = np.column_stack([np.ones(len(z) - 1), z[:-1]])
        beta, *_ = np.linalg.lstsq(X, z[1:], rcond=None)
        self.c = beta[0]
        A = beta[1:].T
        rho = np.max(np.abs(np.linalg.eigvals(A)))
        if rho >= 0.995:
            A = A * (0.995 / rho)
        self.A = A
        self.resid = z[1:] - (self.c + z[:-1] @ self.A.T)
        self.z_last = z[-1]
        self.y_last = yields[-1]
        self.n_factors = n_factors

    def _yields(self, scores: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.maximum(self.mean_y + scores @ self.loadings.T, -0.01)

    def simulate(self, n: int, months: int, rng: np.random.Generator,
                 start_regime: int | None) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int64]]:
        dz = self.z_last.shape[0]
        z = np.empty((n, months, dz))
        prev = np.broadcast_to(self.z_last, (n, dz)).copy()
        draw = rng.integers(0, self.resid.shape[0], (n, months))
        for t in range(months):
            prev = self.c + prev @ self.A.T + self.resid[draw[:, t]]
            z[:, t] = prev
        nf = self.n_factors
        ylds = self._yields(z[:, :, :nf])                      # (n, T, M)
        infl = z[:, :, nf]
        real = np.empty((n, months, len(self.assets)))
        direct = np.expm1(z[:, :, nf + 1:])
        for j, i in enumerate(self.direct_idx):
            real[:, :, i] = direct[:, :, j]
        y_prev_all = np.concatenate([np.broadcast_to(self.y_last, (n, 1, len(self.maturities))), ylds[:, :-1]], axis=1)
        for i in self.bond_idx:
            m = BOND_MATURITY[self.assets[i]]
            col = int(np.argmin(np.abs(self.maturities - m)))
            nom = par_bond_return_vec(y_prev_all[:, :, col], ylds[:, :, col], m)
            real[:, :, i] = (1.0 + nom) / (1.0 + infl) - 1.0
        return np.maximum(real, -0.95), infl, np.zeros((n, months), dtype=np.int64)

    def describe(self) -> dict[str, Any]:
        return {"generator": self.name, "maturities": self.maturities.tolist(), "explained_variance": self.explained,
                "loadings": self.loadings.T.tolist(),
                "var_spectral_radius": float(np.max(np.abs(np.linalg.eigvals(self.A)))),
                "bond_assets": [self.assets[i] for i in self.bond_idx]}
