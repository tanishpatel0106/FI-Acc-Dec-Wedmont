"""M1 cross-asset dependence: rolling and regime-conditional correlation, joint-loss frequencies,
Ledoit-Wolf, DCC-GARCH(1,1), Student-t copula tail dependence, PELT change points, QLIKE scoring."""
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import optimize, stats
from sklearn.covariance import LedoitWolf


def rolling_corr(x: NDArray[np.float64], y: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(window - 1, n):
        a = x[t - window + 1: t + 1]
        b = y[t - window + 1: t + 1]
        sa = a.std()
        sb = b.std()
        if sa > 0 and sb > 0:
            out[t] = float(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb))
    return out


def conditional_corr(x: NDArray[np.float64], y: NDArray[np.float64],
                     labels: NDArray[np.int64]) -> dict[int, dict[str, Any]]:
    out = {}
    for s in np.unique(labels):
        m = labels == s
        if m.sum() > 5:
            out[int(s)] = {"corr": float(np.corrcoef(x[m], y[m])[0, 1]), "n": int(m.sum())}
    return out


def joint_loss_frequency(x: NDArray[np.float64], y: NDArray[np.float64], q: float = 0.10) -> float:
    """P(R_x < q-quantile and R_y < q-quantile); independence benchmark is q^2."""
    qx = np.quantile(x, q)
    qy = np.quantile(y, q)
    return float(np.mean((x < qx) & (y < qy)))


def ledoit_wolf(returns: NDArray[np.float64]) -> tuple[NDArray[np.float64], float]:
    lw = LedoitWolf().fit(returns)
    return lw.covariance_, float(lw.shrinkage_)


def _garch_filter(r: NDArray[np.float64]) -> tuple[NDArray[np.float64], dict[str, float]]:
    from arch import arch_model

    am = arch_model(r * 100.0, mean="Constant", vol="GARCH", p=1, q=1, dist="normal", rescale=False)
    res = am.fit(disp="off")
    sig = np.asarray(res.conditional_volatility) / 100.0
    mu = float(res.params["mu"]) / 100.0
    return (r - mu) / sig, {"omega": float(res.params["omega"]), "alpha": float(res.params["alpha[1]"]),
                            "beta": float(res.params["beta[1]"]), "mu": mu, "sigma": sig.tolist()}


def _dcc_path(z: NDArray[np.float64], a: float, b: float) -> tuple[NDArray[np.float64], float]:
    T, k = z.shape
    qbar = np.cov(z, rowvar=False)
    Q = qbar.copy()
    R = np.empty((T, k, k))
    ll = 0.0
    for t in range(T):
        d = np.sqrt(np.diag(Q))
        Rt = Q / np.outer(d, d)
        R[t] = Rt
        sign, logdet = np.linalg.slogdet(Rt)
        if sign <= 0:
            return R, -1e10
        zt = z[t]
        ll += -0.5 * (logdet + zt @ np.linalg.solve(Rt, zt) - zt @ zt)
        Q = (1 - a - b) * qbar + a * np.outer(zt, zt) + b * Q
    return R, ll


def dcc_garch(returns: NDArray[np.float64]) -> dict[str, Any]:
    """Engle (2002) two-step DCC: univariate GARCH(1,1), then (a, b) by QML."""
    k = returns.shape[1]
    z = np.empty_like(returns)
    uni = []
    for j in range(k):
        z[:, j], info = _garch_filter(returns[:, j])
        uni.append(info)

    def nll(p: NDArray[np.float64]) -> float:
        a, b = p
        if a < 0 or b < 0 or a + b >= 0.999:
            return 1e10
        return -_dcc_path(z, a, b)[1]

    res = optimize.minimize(nll, np.array([0.03, 0.94]), method="Nelder-Mead", options={"xatol": 1e-5})
    a, b = (float(v) for v in res.x)
    R, ll = _dcc_path(z, a, b)
    return {"a": a, "b": b, "loglik": float(ll), "R": R, "univariate": uni, "z": z}


def dcc_forecast_cov(dcc: dict[str, Any], returns: NDArray[np.float64]) -> NDArray[np.float64]:
    """In-sample one-step-ahead covariance path implied by the DCC fit."""
    sig = np.column_stack([np.asarray(u["sigma"]) for u in dcc["univariate"]])
    R = dcc["R"]
    return R * sig[:, :, None] * sig[:, None, :]


def fit_t_copula(x: NDArray[np.float64], y: NDArray[np.float64]) -> dict[str, float]:
    """Bivariate t-copula: rho from Kendall's tau, nu by profile ML; lower-tail dependence coefficient."""
    n = len(x)
    u = stats.rankdata(x) / (n + 1)
    v = stats.rankdata(y) / (n + 1)
    tau = stats.kendalltau(x, y).statistic
    rho = float(np.sin(np.pi * tau / 2))
    best_nu, best_ll = 30.0, -np.inf
    for nu in [2.5, 3, 4, 5, 6, 8, 10, 15, 20, 30, 50]:
        a = stats.t.ppf(u, nu)
        b = stats.t.ppf(v, nu)
        cov = np.array([[1, rho], [rho, 1]])
        ll = float(np.sum(stats.multivariate_t.logpdf(np.column_stack([a, b]), shape=cov, df=nu)
                          - stats.t.logpdf(a, nu) - stats.t.logpdf(b, nu)))
        if ll > best_ll:
            best_nu, best_ll = float(nu), ll
    lam = 2 * stats.t.cdf(-np.sqrt((best_nu + 1) * (1 - rho) / (1 + rho)), best_nu + 1)
    return {"rho": rho, "nu": best_nu, "loglik": best_ll, "tail_dependence": float(lam), "kendall_tau": float(tau)}


def pelt(signal: NDArray[np.float64], penalty: float | None = None, min_size: int = 24) -> list[int]:
    """PELT (Killick et al. 2012) for changes in mean and variance under a Gaussian cost."""
    x = np.asarray(signal, dtype=float)
    n = len(x)
    if penalty is None:
        penalty = 2.0 * 2.0 * np.log(n)  # BIC-style: two parameters per segment
    s1 = np.concatenate([[0.0], np.cumsum(x)])
    s2 = np.concatenate([[0.0], np.cumsum(x * x)])

    def cost(a: int, b: int) -> float:
        m = b - a
        mean = (s1[b] - s1[a]) / m
        var = max((s2[b] - s2[a]) / m - mean * mean, 1e-12)
        return m * (np.log(2 * np.pi * var) + 1)

    F = np.full(n + 1, np.inf)
    F[0] = -penalty
    last = np.zeros(n + 1, dtype=int)
    cands = [0]
    for t in range(min_size, n + 1):
        vals = []
        for s in cands:
            if t - s >= min_size:
                vals.append((F[s] + cost(s, t) + penalty, s))
        if len(vals) == 0:
            continue
        F[t], last[t] = min(vals)
        keep = []
        for v, s in vals:
            if v - penalty <= F[t]:
                keep.append(s)
        for s in cands:
            if t - s < min_size:
                keep.append(s)
        keep.append(t)
        cands = sorted(set(keep))
    cps = []
    t = n
    while t > 0:
        s = int(last[t])
        if s > 0:
            cps.append(s)
        t = s
    return sorted(cps)


def qlike(cov_forecasts: NDArray[np.float64], realised: NDArray[np.float64]) -> float:
    """Mean QLIKE loss: log det Sigma + r' Sigma^-1 r (lower is better)."""
    losses = []
    for t in range(len(realised)):
        S = cov_forecasts[t]
        sign, logdet = np.linalg.slogdet(S)
        if sign <= 0:
            continue
        r = realised[t]
        losses.append(logdet + r @ np.linalg.solve(S, r))
    return float(np.mean(losses))


def min_var_realised_vol(cov_forecasts: NDArray[np.float64], realised: NDArray[np.float64]) -> float:
    rets = []
    k = realised.shape[1]
    for t in range(len(realised)):
        inv = np.linalg.pinv(cov_forecasts[t])
        w = inv @ np.ones(k)
        w = w / w.sum()
        rets.append(float(w @ realised[t]))
    return float(np.std(rets) * np.sqrt(12))


def covariance_forecast_horse_race(returns: NDArray[np.float64], window: int = 60,
                                   dcc_cov: NDArray[np.float64] | None = None) -> list[dict[str, Any]]:
    """Out-of-sample one-month-ahead covariance forecasts scored on unseen months only."""
    T, k = returns.shape
    models: dict[str, list[NDArray[Any]]] = {"rolling_60m": [], "ewma_0.97": [], "ledoit_wolf_60m": []}
    if dcc_cov is not None:
        models["dcc_garch"] = []
    ewma = np.cov(returns[:window], rowvar=False)
    realised = []
    for t in range(window, T):
        hist = returns[t - window: t]
        models["rolling_60m"].append(np.cov(hist, rowvar=False))
        models["ledoit_wolf_60m"].append(LedoitWolf().fit(hist).covariance_)
        r_prev = returns[t - 1] - hist.mean(axis=0)
        ewma = 0.97 * ewma + 0.03 * np.outer(r_prev, r_prev)
        models["ewma_0.97"].append(ewma.copy())
        if dcc_cov is not None:
            models["dcc_garch"].append(dcc_cov[t])
        realised.append(returns[t] - hist.mean(axis=0))
    real = np.array(realised)
    out: list[dict[str, Any]] = []
    for name, fc in models.items():
        arr = np.array(fc)
        out.append({"model": name, "qlike": qlike(arr, real), "minvar_vol": min_var_realised_vol(arr, real)})
    out.sort(key=lambda r: r["qlike"])
    return out
