"""Point-in-time decision signals for simulated paths (brief 1.2 item 1, 5.1).

A scenario tensor carries `regime[j, t]`, the state that *generated* R[j, t]. Using it to choose the
weights that earn R[j, t] is look-ahead. Decision rules must instead use information available at the
decision timestamp:

* Markov switching: the Hamilton-filter predicted probability xi_{t|t-1} computed on the simulated
  path itself (returns and inflation through t-1), with the as-of filtered state at t = 0;
* bootstrap / historical: the point-in-time filtered label of the *previous* sampled month;
* `oracle`: the contemporaneous latent state, available only as a labelled upper bound.
"""
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from lifecycle.engine.scenarios.base import ScenarioTensor, to_features

SignalMode = Literal["filtered_lagged", "lagged_label", "oracle", "none"]


def _logdens_batch(x: NDArray[np.float64], mu: NDArray[np.float64], sig: NDArray[np.float64]) -> NDArray[np.float64]:
    """x (N, d) -> (N, K) Gaussian log densities."""
    N, d = x.shape
    K = mu.shape[0]
    out = np.empty((N, K))
    for k in range(K):
        L = np.linalg.cholesky(sig[k])
        diff = x - mu[k]
        z = np.linalg.solve(L, diff.T).T
        out[:, k] = -0.5 * np.sum(z * z, axis=1) - np.sum(np.log(np.diag(L))) - 0.5 * d * np.log(2 * np.pi)
    return out


def filtered_predicted(model: Any, tensor: ScenarioTensor) -> NDArray[np.float64]:
    """Predicted regime probabilities xi_{t|t-1} (N, T, K) on each simulated path."""
    N, T, _ = tensor.real_returns.shape
    K = int(model.k)
    P = model.P
    feats = to_features(tensor.real_returns.reshape(N * T, -1), tensor.inflation.reshape(N * T)).reshape(N, T, -1)
    prior = np.broadcast_to(model.filtered[-1] @ P, (N, K)).copy()
    out = np.empty((N, T, K))
    for t in range(T):
        out[:, t] = prior
        ld = _logdens_batch(feats[:, t], model.mu, model.sigma)
        m = ld.max(axis=1, keepdims=True)
        joint = prior * np.exp(ld - m)
        filt = joint / joint.sum(axis=1, keepdims=True)
        prior = filt @ P
    return out


def decision_regime(tensor: ScenarioTensor, model: Any | None = None, mode: SignalMode = "filtered_lagged",
                    asof_label: int = 0) -> tuple[NDArray[np.int64], dict[str, Any]]:
    """Regime index usable by a policy at month t, plus a description for provenance."""
    N, T = tensor.regime.shape
    if tensor.n_regimes <= 1 or mode == "none":
        return np.zeros((N, T), dtype=np.int64), {"signal": "none", "tradable": True}
    if mode == "oracle":
        return tensor.regime.copy(), {"signal": "oracle (contemporaneous latent state)", "tradable": False,
                                      "warning": "oracle upper bound - not a tradable benchmark"}
    gen = tensor.meta.get("generator")
    if gen == "markov_switching" and model is not None and hasattr(model, "P"):
        pred = filtered_predicted(model, tensor)
        return np.argmax(pred, axis=2).astype(np.int64), {
            "signal": "Hamilton filter on the simulated path, predicted xi_{t|t-1}", "tradable": True}
    dec = np.empty((N, T), dtype=np.int64)
    dec[:, 0] = asof_label
    dec[:, 1:] = tensor.regime[:, :-1]
    return dec, {"signal": "filtered history label of the previous month (one-month lag)", "tradable": True}
