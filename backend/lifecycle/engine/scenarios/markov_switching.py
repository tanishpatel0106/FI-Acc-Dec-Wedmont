"""Gaussian Markov-switching model (Hamilton 1989) estimated by EM: Hamilton filter + Kim smoother.

Only filtered probabilities feed decision rules; smoothed probabilities are descriptive.
Regimes are ordered by mean inflation so labels are stable across re-estimations.
"""
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.stats import multivariate_normal

from lifecycle.engine.scenarios.base import from_features, to_features


def _logpdf_all(x: NDArray[np.float64], mu: NDArray[np.float64], sig: NDArray[np.float64]) -> NDArray[np.float64]:
    K = mu.shape[0]
    out = np.empty((x.shape[0], K))
    for k in range(K):
        out[:, k] = multivariate_normal.logpdf(x, mean=mu[k], cov=sig[k], allow_singular=True)
    return out


def hamilton_filter(logdens: NDArray[np.float64], P: NDArray[np.float64],
                    pi0: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
    """Returns filtered probs xi_{t|t}, predicted probs xi_{t|t-1} and the log-likelihood."""
    T, K = logdens.shape
    filt = np.empty((T, K))
    pred = np.empty((T, K))
    ll = 0.0
    prior = pi0
    for t in range(T):
        pred[t] = prior
        m = logdens[t].max()
        joint = prior * np.exp(logdens[t] - m)
        tot = joint.sum()
        ll += np.log(tot) + m
        filt[t] = joint / tot
        prior = filt[t] @ P
    return filt, pred, float(ll)


def kim_smoother(filt: NDArray[np.float64], pred: NDArray[np.float64],
                 P: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    T, K = filt.shape
    smooth = np.empty((T, K))
    smooth[-1] = filt[-1]
    joint_sum = np.zeros((K, K))
    for t in range(T - 2, -1, -1):
        ratio = smooth[t + 1] / np.maximum(pred[t + 1], 1e-300)
        smooth[t] = filt[t] * (P @ ratio)
        joint = filt[t][:, None] * P * ratio[None, :]
        joint_sum += joint
    return smooth, joint_sum


class MarkovSwitching:
    name = "markov_switching"
    deterministic = False

    def __init__(self, real: NDArray[np.float64], infl: NDArray[np.float64], k: int = 2,
                 max_iter: int = 300, tol: float = 1e-7, shrink: float = 0.05) -> None:
        x = to_features(real, infl)
        self.n_assets = real.shape[1]
        self.k = k
        self.n_regimes = k
        T, d = x.shape
        # deterministic initialisation: quantiles of trailing 12m inflation
        trail = np.convolve(infl, np.ones(12) / 12, mode="same")
        cuts = np.quantile(trail, np.linspace(0, 1, k + 1)[1:-1])
        init = np.searchsorted(cuts, trail)
        mu = np.array([x[init == s].mean(axis=0) if np.any(init == s) else x.mean(axis=0) for s in range(k)])
        sig = np.array([np.cov(x[init == s], rowvar=False) + 1e-8 * np.eye(d) if np.sum(init == s) > d
                        else np.cov(x, rowvar=False) for s in range(k)])
        P = np.full((k, k), 0.05 / max(k - 1, 1))
        np.fill_diagonal(P, 0.95)
        pi0 = np.full(k, 1.0 / k)
        prev = -np.inf
        for it in range(max_iter):
            logd = _logpdf_all(x, mu, sig)
            filt, pred, ll = hamilton_filter(logd, P, pi0)
            smooth, joint = kim_smoother(filt, pred, P)
            # M-step
            P = joint / np.maximum(joint.sum(axis=1, keepdims=True), 1e-300)
            pi0 = smooth[0]
            for s in range(k):
                w = smooth[:, s]
                ws = w.sum()
                mu[s] = (w[:, None] * x).sum(axis=0) / ws
                diff = x - mu[s]
                S = (w[:, None] * diff).T @ diff / ws
                sig[s] = (1 - shrink) * S + shrink * np.diag(np.diag(S)) + 1e-10 * np.eye(d)
            if abs(ll - prev) < tol * max(1.0, abs(ll)):
                prev = ll
                break
            prev = ll
        self.iterations = it + 1
        order = np.argsort(mu[:, -1])  # ascending mean inflation
        self.mu = mu[order]
        self.sigma = sig[order]
        self.P = P[np.ix_(order, order)]
        logd = _logpdf_all(x, self.mu, self.sigma)
        self.pi0 = pi0[order]
        self.filtered, pred, self.loglik = hamilton_filter(logd, self.P, self.pi0)
        self.smoothed, _ = kim_smoother(self.filtered, pred, self.P)
        n_par = (k - 1) + k * (k - 1) + k * d + k * d * (d + 1) / 2
        self.bic = float(-2 * self.loglik + n_par * np.log(T))
        self.chol = np.array([np.linalg.cholesky(self.sigma[s]) for s in range(k)])
        evals, evecs = np.linalg.eig(self.P.T)
        st = np.real(evecs[:, np.argmin(np.abs(evals - 1))])
        self.stationary = st / st.sum()
        self.labels = np.argmax(self.filtered, axis=1).astype(np.int64)

    def regime_names(self) -> list[str]:
        """Descriptive names assigned after inspecting the estimates (inflation and equity vol ranks)."""
        names = []
        eq_vol = np.sqrt(self.sigma[:, 0, 0] * 12)
        for s in range(self.k):
            infl = self.mu[s, -1] * 12
            tag = "inflationary" if infl > 0.04 else ("disinflationary" if infl < 0.025 else "moderate inflation")
            vol = "high-vol" if eq_vol[s] > np.median(eq_vol) and self.k > 1 else "low-vol"
            if self.k == 1:
                vol = ""
            names.append((tag + " " + vol).strip())
        return names

    def simulate(self, n: int, months: int, rng: np.random.Generator,
                 start_regime: int | None) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int64]]:
        k = self.k
        d = self.mu.shape[1]
        cum = np.cumsum(self.P, axis=1)
        if start_regime is None:
            # start from the latest filtered (point-in-time) regime probabilities
            p0 = self.filtered[-1] @ self.P
            state = np.searchsorted(np.cumsum(p0), rng.random(n))
        else:
            state = np.full(n, int(start_regime))
        state = np.minimum(state, k - 1)
        regimes = np.empty((n, months), dtype=np.int64)
        x = np.empty((n, months, d))
        z = rng.standard_normal((n, months, d))
        for t in range(months):
            if t > 0:
                u = rng.random(n)
                state = np.minimum((u[:, None] > cum[state]).sum(axis=1), k - 1)
            regimes[:, t] = state
            for s in range(k):
                m = state == s
                if np.any(m):
                    x[m, t] = self.mu[s] + z[m, t] @ self.chol[s].T
        real, infl = from_features(x, self.n_assets)
        return np.maximum(real, -0.95), infl, regimes

    def describe(self) -> dict[str, Any]:
        return {"generator": self.name, "k": self.k, "loglik": self.loglik, "bic": self.bic,
                "iterations": self.iterations, "transition": self.P.tolist(),
                "stationary": self.stationary.tolist(), "names": self.regime_names(),
                "mu_annual": (self.mu * 12).tolist(),
                "vol_annual": [np.sqrt(np.diag(self.sigma[s]) * 12).tolist() for s in range(self.k)],
                "expected_duration_months": [float(1 / max(1 - self.P[s, s], 1e-9)) for s in range(self.k)]}


def select_k(real: NDArray[np.float64], infl: NDArray[np.float64], candidates: tuple[int, ...] = (2, 3)) -> dict[str, Any]:
    out = {}
    for k in candidates:
        m = MarkovSwitching(real, infl, k=k)
        out[k] = m.bic
    best = min(out, key=lambda kk: out[kk])
    return {"bic": out, "best_k": best}
