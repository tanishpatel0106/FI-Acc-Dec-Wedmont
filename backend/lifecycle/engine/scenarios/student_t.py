"""Multivariate Student-t (i.i.d.) on log real returns + inflation; nu by ML, scatter shrunk."""
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import special
from sklearn.covariance import ledoit_wolf

from lifecycle.engine.scenarios.base import from_features, to_features


def _t_loglik(x: NDArray[np.float64], mu: NDArray[np.float64], sigma: NDArray[np.float64], nu: float) -> float:
    n, d = x.shape
    chol = np.linalg.cholesky(sigma)
    z = np.linalg.solve(chol, (x - mu).T)
    maha = np.sum(z * z, axis=0)
    logdet = 2.0 * np.sum(np.log(np.diag(chol)))
    ll = (special.gammaln((nu + d) / 2) - special.gammaln(nu / 2) - 0.5 * d * np.log(nu * np.pi)
          - 0.5 * logdet - 0.5 * (nu + d) * np.log1p(maha / nu))
    return float(np.sum(ll))


def fit_mvt(x: NDArray[np.float64], nu: float, iters: int = 200) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """EM for location/scatter at fixed nu."""
    n, d = x.shape
    mu = x.mean(axis=0)
    sigma = np.cov(x, rowvar=False) * (nu - 2) / nu if nu > 2 else np.cov(x, rowvar=False)
    for _ in range(iters):
        diff = x - mu
        inv = np.linalg.inv(sigma)
        maha = np.einsum("ij,jk,ik->i", diff, inv, diff)
        w = (nu + d) / (nu + maha)
        mu_new = (w[:, None] * x).sum(axis=0) / w.sum()
        diff = x - mu_new
        sigma_new = (w[:, None] * diff).T @ diff / n
        if np.max(np.abs(mu_new - mu)) < 1e-10 and np.max(np.abs(sigma_new - sigma)) < 1e-12:
            mu, sigma = mu_new, sigma_new
            break
        mu, sigma = mu_new, sigma_new
    return np.asarray(mu, dtype=np.float64), np.asarray(sigma, dtype=np.float64)


class MultivariateT:
    name = "student_t"
    deterministic = False
    n_regimes = 1

    def __init__(self, real: NDArray[np.float64], infl: NDArray[np.float64], nu: float | None = None) -> None:
        x = to_features(real, infl)
        self.n_assets = real.shape[1]
        grid = [nu] if nu is not None else [3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0, 30.0]
        best = None
        for g in grid:
            mu, sig = fit_mvt(x, g)
            ll = _t_loglik(x, mu, sig, g)
            if best is None or ll > best[0]:
                best = (ll, g, mu, sig)
        assert best is not None
        self.loglik, self.nu, self.mu, scatter = best
        # the t is symmetric, so pin its centre to the sample mean of the log returns (first moment preserved)
        self.mu = x.mean(axis=0)
        # Ledoit-Wolf intensity applied toward the diagonal of the fitted scatter
        _, shrink = ledoit_wolf(x)
        self.shrinkage = float(shrink)
        self.scatter = (1 - shrink) * scatter + shrink * np.diag(np.diag(scatter))
        self.chol = np.linalg.cholesky(self.scatter)

    def simulate(self, n: int, months: int, rng: np.random.Generator,
                 start_regime: int | None) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int64]]:
        d = self.mu.shape[0]
        z = rng.standard_normal((n, months, d)) @ self.chol.T
        chi = rng.chisquare(self.nu, (n, months, 1))
        x = self.mu + z * np.sqrt(self.nu / chi)
        real, infl = from_features(x, self.n_assets)
        real = np.maximum(real, -0.95)
        return real, infl, np.zeros((n, months), dtype=np.int64)

    def describe(self) -> dict[str, Any]:
        cov = self.scatter * self.nu / (self.nu - 2) if self.nu > 2 else self.scatter
        return {"generator": self.name, "nu": self.nu, "loglik": self.loglik, "shrinkage": self.shrinkage,
                "mu_annual": (self.mu * 12).tolist(), "vol_annual": np.sqrt(np.diag(cov) * 12).tolist()}
