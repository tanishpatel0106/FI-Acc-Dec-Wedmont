"""Resolve a PolicySpec into a concrete WeightPolicy (fitting on seed-set A where needed)."""
from collections.abc import Callable
from typing import Any

import numpy as np

from lifecycle.data import panel
from lifecycle.engine.lifecycle import policies as pol
from lifecycle.engine.lifecycle.simulator import Context, Spending, ce_annual, evaluate
from lifecycle.engine.optimize import parametric, static
from lifecycle.runs.spec import PolicySpec

Progress = Callable[[str, float], None]


def _noop(stage: str, frac: float) -> None:
    return None


def sleeves(assets: tuple[str, ...], params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    risky, safe = pol.default_sleeves(assets)
    if "risky_weights" in params:
        risky = pol.vector(params["risky_weights"], assets)
    if "safe_weights" in params:
        safe = pol.vector(params["safe_weights"], assets)
    return risky, safe


def benchmark_policy(name: str, ctx: Context, spending: Spending, train: Context | None = None) -> tuple[pol.WeightPolicy, dict]:
    assets = ctx.tensor.assets
    T = ctx.months
    if name == "sixty_forty":
        return pol.constant_mix(pol.vector({"us_eq": 0.6, "ust_10y": 0.4}, assets), T, "60/40"), {}
    risky, safe = pol.default_sleeves(assets)
    if name == "target_date":
        return pol.target_date(ctx.investor.start_age, T, risky, safe), {}
    if name == "best_constant":
        fit_ctx = train if train is not None else ctx
        share, ce, table = parametric.best_constant_share(fit_ctx, risky, safe, spending)
        w = share * risky + (1 - share) * safe
        return pol.constant_mix(w, T, "best constant mix (%.0f%% growth)" % (share * 100)), {"growth_share": share,
                                                                                             "grid": table}
    raise ValueError("unknown benchmark: " + name)


def _hist_real(assets: tuple[str, ...], universe: panel.UniverseData) -> np.ndarray:
    return universe.real[list(assets)].to_numpy()


def resolve(spec: PolicySpec, ctx: Context, train: Context, spending: Spending, universe: panel.UniverseData,
            progress: Progress = _noop) -> tuple[pol.WeightPolicy, dict[str, Any], Spending]:
    """Returns (policy, description, spending) - spending may be re-tuned for utility-optimal rules."""
    assets = ctx.tensor.assets
    T = ctx.months
    params = dict(spec.params)
    gamma = ctx.prefs.gamma
    info: dict[str, Any] = {"type": spec.type}
    t = spec.type

    if t == "constant_mix":
        if spec.weights is None:
            raise ValueError("constant_mix needs weights")
        w = pol.vector(spec.weights, assets)
        return pol.constant_mix(w, T), info, spending
    if t in ("sixty_forty", "target_date", "best_constant"):
        p, extra = benchmark_policy(t, ctx, spending, train)
        info.update(extra)
        return p, info, spending
    if t == "glidepath":
        risky, safe = sleeves(assets, params)
        if params.get("optimize", True) and "theta0" not in params:
            progress("optimising", 0.1)
            t0, t1, ce = parametric.fit_glidepath(train, risky, safe, spending)
            info.update({"theta0": t0, "theta1": t1, "ce_train": ce})
        else:
            t0 = float(params.get("theta0", 0.6))
            t1 = float(params.get("theta1", -0.1))
            info.update({"theta0": t0, "theta1": t1})
        return pol.linear_glidepath(ctx.investor.start_age, T, t0, t1, risky, safe), info, spending
    if t in ("risk_parity", "min_variance", "mean_variance", "mean_cvar"):
        hist = _hist_real(assets, universe)
        mu, cov = static.shrunk_moments(hist)
        if t == "risk_parity":
            w = static.risk_parity(cov)
            info["risk_contributions"] = dict(zip(assets, static.risk_contributions(w, cov).tolist()))
        elif t == "min_variance":
            w = static.min_variance(cov)
        elif t == "mean_variance":
            w = static.mean_variance(mu, cov, float(params.get("risk_aversion", gamma)))
        else:
            w = static.mean_cvar(hist, float(params.get("alpha", 0.95)),
                                 float(params.get("risk_aversion", 0.05 * gamma)))
        info["calibration"] = "historical real returns, Ledoit-Wolf covariance"
        return pol.constant_mix(w, T, t.replace("_", " ")), info, spending
    if t == "utility_static":
        progress("optimising", 0.1)
        n = len(assets)

        def obj(w: np.ndarray) -> float:
            out = evaluate(train, pol.constant_mix(w, train.months), spending)
            return ce_annual(out, gamma)[0]

        risky, safe = pol.default_sleeves(assets)
        start = 0.5 * risky + 0.5 * safe
        w, ce = static.maximize_objective(obj, n, start=start, maxiter=int(params.get("maxiter", 40)))
        info["ce_train"] = ce
        return pol.constant_mix(w, T, "static CRRA-optimal mix"), info, spending
    if t == "regime":
        K = max(int(ctx.tensor.n_regimes), 1)
        risky, safe = sleeves(assets, params)
        if "shares" in params:
            shares = np.asarray(params["shares"], dtype=float)[:K]
        else:
            progress("optimising", 0.1)
            shares = np.full(K, 0.6)
            grid = np.linspace(0, 1, 11)
            for _sweep in range(2):
                for k in range(K):
                    best = (-np.inf, shares[k])
                    for g in grid:
                        trial = shares.copy()
                        trial[k] = g
                        per = trial[:, None] * risky[None, :] + (1 - trial[:, None]) * safe[None, :]
                        out = evaluate(train, pol.regime_dependent(per, train.months), spending)
                        ce = ce_annual(out, gamma)[0]
                        if ce > best[0]:
                            best = (ce, g)
                    shares[k] = best[1]
        per = shares[:, None] * risky[None, :] + (1 - shares[:, None]) * safe[None, :]
        info["growth_share_by_regime"] = shares.tolist()
        return pol.regime_dependent(per, T), info, spending
    if t == "bucket":
        risky, safe = sleeves(assets, params)
        if "safe_weights" not in params:
            ladder = {k: v for k, v in {"tips": 0.6, "ust_5y": 0.2, "ust_10y": 0.2}.items() if k in assets}
            if "tips" not in ladder:
                ladder = {k: v for k, v in {"ust_5y": 0.5, "ust_10y": 0.5}.items() if k in assets}
            safe = pol.vector(ladder, assets)
        years = float(params.get("years", 7.0))
        info.update({"years": years, "ladder": dict(zip(assets, safe.tolist()))})
        return pol.bucket(years, risky, safe, ctx.investor.start_age, T), info, spending
    if t == "parametric":
        risky, safe = sleeves(assets, params)
        progress("optimising", 0.1)
        use_regime = bool(params.get("use_regime", ctx.tensor.n_regimes > 1))
        optimise_spend = spec.spending_rule == "utility_optimal"
        if "theta" in params:
            theta = np.zeros(4)
            th = np.asarray(params["theta"], dtype=float)
            theta[: len(th)] = th
            return pol.parametric(theta, risky, safe, T), {"theta": theta.tolist(), **info}, spending
        a0, _, _ = parametric.best_constant_share(train, risky, safe, spending, np.linspace(0, 1, 6))
        fit = parametric.fit_parametric(train, ctx, risky, safe, spending, use_regime=use_regime,
                                        optimise_spending=optimise_spend, starts=[[a0, 0.0, 0.0]], max_iter=120)
        info.update({"theta": fit.theta.tolist(), "ce_train": fit.ce_train, "ce_test": fit.ce_test,
                     "overfit_gap": fit.overfit_gap, "evaluations": fit.evaluations,
                     "theta_labels": ["intercept", "age slope (per decade)", "funded-ratio slope", "regime shift"]})
        sp = spending
        if fit.amort_rate is not None:
            from dataclasses import replace

            sp = replace(spending, amort_rate=fit.amort_rate)
            info["amort_rate"] = fit.amort_rate
        return pol.parametric(fit.theta, risky, safe, T), info, sp
    raise ValueError("policy type not supported in the monthly engine: " + t)
