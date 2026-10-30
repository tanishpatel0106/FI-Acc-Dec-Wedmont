"""Derived market analytics for the Research Lab and Fixed Income panel (cached by catalog hash).

Only derived statistics leave the server: moments, drawdowns, rolling/regime correlations,
model estimates. Raw return observations are never returned.
"""
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from lifecycle.data import panel
from lifecycle.engine import dependence, fixed_income
from lifecycle.engine.scenarios.markov_switching import MarkovSwitching


def _dates(idx: pd.DatetimeIndex) -> list[str]:
    return [d.date().isoformat() for d in idx]


def _key() -> str:
    return panel.catalog_hash()


def returns_summary(universe: str, start: str | None, end: str | None) -> dict[str, Any]:
    return _returns_summary(universe, start, end, _key())


@lru_cache(maxsize=16)
def _returns_summary(universe: str, start: str | None, end: str | None, ck: str) -> dict[str, Any]:
    u = panel.universe_data(universe, start, end)
    rows = []
    dd_series = {}
    vol_series = {}
    rf = u.nominal["tbill"] if "tbill" in u.nominal.columns else None
    for a in u.assets:
        nom = u.nominal[a]
        real = u.real[a]
        wealth = (1 + real).cumprod()
        dd = wealth / wealth.cummax() - 1
        excess = nom - rf if rf is not None else nom
        rows.append({"asset": a, "label": panel.asset_label(a), "mean_nominal": float(nom.mean() * 12),
                     "mean_real": float(real.mean() * 12), "geo_real": float(wealth.iloc[-1] ** (12 / len(real)) - 1),
                     "vol": float(nom.std() * np.sqrt(12)), "skew": float(stats.skew(nom)),
                     "kurtosis": float(stats.kurtosis(nom, fisher=False)), "max_drawdown_real": float(dd.min()),
                     "sharpe": float(excess.mean() / excess.std() * np.sqrt(12)) if excess.std() > 0 else None,
                     "n_months": int(len(nom))})
        dd_series[a] = dd.round(5).tolist()
        vol_series[a] = (nom.rolling(36).std() * np.sqrt(12)).round(5).tolist()
    corr = u.real.corr().round(4)
    return {"universe": universe, "window": [u.start.date().isoformat(), u.end.date().isoformat()],
            "assets": list(u.assets), "excluded": u.excluded, "rows": rows, "dates": _dates(u.real.index),
            "drawdowns": dd_series, "rolling_vol_36m": vol_series,
            "correlation": {"assets": list(u.assets), "matrix": corr.to_numpy().tolist()},
            "inflation": {"mean": float(u.inflation.mean() * 12), "vol": float(u.inflation.std() * np.sqrt(12))}}


def dependence_view(universe: str, a: str, b: str, start: str | None, end: str | None) -> dict[str, Any]:
    return _dependence(universe, a, b, start, end, _key())


@lru_cache(maxsize=16)
def _dependence(universe: str, a: str, b: str, start: str | None, end: str | None, ck: str) -> dict[str, Any]:
    u = panel.universe_data(universe, start, end)
    if a not in u.assets or b not in u.assets:
        raise KeyError("assets not in universe: " + a + ", " + b)
    x = u.nominal[a].to_numpy()
    y = u.nominal[b].to_numpy()
    idx = u.nominal.index
    rolling = {str(w): [None if not np.isfinite(v) else round(float(v), 4) for v in dependence.rolling_corr(x, y, w)]
               for w in (12, 36, 60)}
    yoy = (1 + u.inflation).rolling(12).apply(np.prod, raw=True) - 1
    infl_regime = (yoy > 0.03).astype(int).to_numpy()
    infl_cond = dependence.conditional_corr(x, y, infl_regime)
    decades = {}
    for dec in sorted(set((d.year // 10) * 10 for d in idx)):
        m = np.array([(d.year // 10) * 10 == dec for d in idx])
        if m.sum() >= 36:
            decades[str(dec) + "s"] = {"corr": float(np.corrcoef(x[m], y[m])[0, 1]),
                                       "joint_loss": dependence.joint_loss_frequency(x[m], y[m]), "n": int(m.sum())}
    jl_by_infl = {}
    for s in (0, 1):
        m = infl_regime == s
        if m.sum() >= 36:
            jl_by_infl["high_inflation" if s == 1 else "low_inflation"] = {
                "joint_loss": dependence.joint_loss_frequency(x[m], y[m]), "corr": float(np.corrcoef(x[m], y[m])[0, 1]),
                "n": int(m.sum())}
    cop = dependence.fit_t_copula(x, y)
    dcc = dependence.dcc_garch(np.column_stack([x, y]))
    dcc_corr = dcc["R"][:, 0, 1]
    # PELT on the standardised cross-product, whose local mean is the local correlation
    zc = ((x - x.mean()) / x.std()) * ((y - y.mean()) / y.std())
    cps = dependence.pelt(zc, min_size=60)
    cp_dates = [idx[c].date().isoformat() for c in cps]
    # model comparison is out of sample: one-month-ahead covariance forecasts scored with QLIKE
    rets = np.column_stack([x, y])
    horse = dependence.covariance_forecast_horse_race(rets, 60, dependence.dcc_forecast_cov(dcc, rets))
    lw_cov, lw_shrink = dependence.ledoit_wolf(u.nominal.to_numpy())
    return {"universe": universe, "a": a, "b": b, "dates": _dates(idx), "rolling": rolling,
            "full_sample_corr": float(np.corrcoef(x, y)[0, 1]),
            "inflation_regime": {"definition": "YoY CPI above 3%", "conditional": infl_cond,
                                 "series": infl_regime.tolist()},
            "by_decade": decades, "joint_loss_by_inflation": jl_by_infl,
            "joint_loss_full": dependence.joint_loss_frequency(x, y), "independence_benchmark": 0.01,
            "t_copula": cop, "dcc": {"a": dcc["a"], "b": dcc["b"], "corr": np.round(dcc_corr, 4).tolist()},
            "change_points": {"method": "PELT (mean/variance, BIC penalty) on the standardised return cross-product",
                              "dates": cp_dates},
            "forecast_comparison": horse, "ledoit_wolf_shrinkage": lw_shrink,
            "caveat": "DCC parameters are estimated on the full sample; other forecasts are strictly rolling"}


def regimes_view(universe: str, k: int, start: str | None, end: str | None) -> dict[str, Any]:
    return _regimes(universe, k, start, end, _key())


@lru_cache(maxsize=16)
def _regimes(universe: str, k: int, start: str | None, end: str | None, ck: str) -> dict[str, Any]:
    u = panel.universe_data(universe, start, end)
    real = u.real_array()
    infl = u.inflation.to_numpy()
    ms = MarkovSwitching(real, infl, k=k)
    bic = {}
    for kk in (1, 2, 3):
        bic[str(kk)] = ms.bic if kk == k else MarkovSwitching(real, infl, k=kk).bic
    names = list(u.assets) + ["inflation"]
    corr = []
    for s in range(k):
        d = np.sqrt(np.diag(ms.sigma[s]))
        corr.append((ms.sigma[s] / np.outer(d, d)).round(3).tolist())
    rec = None
    if panel.has_series("s_usrec"):
        r = panel.series("s_usrec").reindex(u.real.index)
        rec = [None if not np.isfinite(v) else int(v) for v in r.to_numpy()]
    return {"universe": universe, "k": k, "dates": _dates(u.real.index), "series": names,
            "filtered": ms.filtered.round(4).tolist(), "smoothed": ms.smoothed.round(4).tolist(),
            "mu_annual": (ms.mu * 12).round(5).tolist(), "vol_annual": [np.sqrt(np.diag(ms.sigma[s]) * 12).round(5).tolist()
                                                                        for s in range(k)],
            "corr": corr, "transition": ms.P.round(4).tolist(), "stationary": ms.stationary.round(4).tolist(),
            "names": ms.regime_names(), "bic": bic, "loglik": ms.loglik,
            "expected_duration_months": [float(1 / max(1 - ms.P[s, s], 1e-9)) for s in range(k)],
            "usrec": rec, "note": "filtered probabilities drive decisions; smoothed are descriptive; "
                                  "USREC is shown for retrospective evaluation only"}


def factors_view(universe: str) -> dict[str, Any]:
    return _factors(universe, _key())


@lru_cache(maxsize=8)
def _factors(universe: str, ck: str) -> dict[str, Any]:
    u = panel.universe_data(universe)
    fac_ids = [f for f in ["ff_mktrf", "ff_smb", "ff_hml", "ff_rmw", "ff_cma", "ff_umd"] if panel.has_series(f)]
    F = panel.wide(fac_ids + ["ff_rf"])
    rows = []
    for a in u.assets:
        df = pd.concat([u.nominal[a].rename("r"), F], axis=1).dropna()
        if len(df) < 36:
            continue
        yv = (df["r"] - df["ff_rf"]).to_numpy()
        X = np.column_stack([np.ones(len(df)), df[fac_ids].to_numpy()])
        beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
        resid = yv - X @ beta
        r2 = 1 - resid.var() / yv.var() if yv.var() > 0 else 0.0
        se = np.sqrt(np.diag(np.linalg.pinv(X.T @ X)) * resid.var())
        rows.append({"asset": a, "alpha_annual": float(beta[0] * 12), "alpha_t": float(beta[0] / se[0]),
                     "betas": dict(zip([f[3:] for f in fac_ids], beta[1:].round(4).tolist())), "r2": float(r2),
                     "n": int(len(df))})
    return {"universe": universe, "factors": [f[3:] for f in fac_ids], "rows": rows}


def _curve_on(date: str | None, kind: str) -> tuple[str, np.ndarray, np.ndarray]:
    if kind == "nominal":
        ids = ["gsw_nom_%02d" % m for m in range(1, 31)]
    else:
        ids = ["gsw_real_%02d" % m for m in range(2, 21)]
    w = panel.wide(ids)
    if w.shape[1] == 0:
        raise KeyError("no " + kind + " curve in panel")
    w = w.dropna(how="all")
    if date is None:
        ts = w.index[-1]
    else:
        ts = w.index[w.index <= pd.Timestamp(date) + pd.offsets.MonthEnd(0)][-1]
    row = w.loc[ts].dropna()
    mats = np.array([int(c[-2:]) for c in row.index], dtype=float)
    return ts.date().isoformat(), mats, row.to_numpy()


def yield_curve_view(date: str | None, withdrawal: float, years: int) -> dict[str, Any]:
    return _yield_curve(date, withdrawal, years, _key())


@lru_cache(maxsize=32)
def _yield_curve(date: str | None, withdrawal: float, years: int, ck: str) -> dict[str, Any]:
    d, m, z = _curve_on(date, "nominal")
    prev_date = (pd.Timestamp(d) - pd.DateOffset(years=1)).date().isoformat()
    _, m_prev, z_prev = _curve_on(prev_date, "nominal")
    out: dict[str, Any] = {"date": d, "nominal": {"maturities": m.tolist(), "zero": z.tolist()},
                           "nominal_1y_ago": {"date": prev_date, "maturities": m_prev.tolist(), "zero": z_prev.tolist()}}
    par = fixed_income.zero_to_par(z, m)
    out["nominal"]["par"] = [par[k] for k in sorted(par)]
    out["risk_table"] = fixed_income.risk_table({k: par[k] for k in [1.0, 2.0, 5.0, 7.0, 10.0, 20.0, 30.0] if k in par})
    out["shocks"] = fixed_income.shock_table(m, z, [2.0, 5.0, 10.0, 30.0], [-100, -50, -25, 25, 50, 100, 200])
    steep = fixed_income.twist(m, -25, 25)
    flat = fixed_income.twist(m, 25, -25)
    twists = []
    for mat in [2.0, 5.0, 10.0, 30.0]:
        y = par.get(mat, float(np.interp(mat, m, z)))
        p0 = fixed_income.price_on_curve(y, mat, m, z)
        twists.append({"maturity": mat, "steepener": fixed_income.price_on_curve(y, mat, m, z, steep) / p0 - 1,
                       "flattener": fixed_income.price_on_curve(y, mat, m, z, flat) / p0 - 1})
    out["twists"] = twists
    # PCA on monthly yield changes 1Y-30Y where the curve is complete
    full_ids = ["gsw_nom_%02d" % k for k in [1, 2, 3, 5, 7, 10, 15, 20, 25, 30]]
    hist = panel.wide(full_ids).dropna()
    pca = fixed_income.pca_yield_changes(hist.to_numpy(), 3)
    out["pca"] = {"maturities": [1, 2, 3, 5, 7, 10, 15, 20, 25, 30], "loadings": pca["loadings"].round(4).tolist(),
                  "explained": pca["explained"].round(4).tolist(), "labels": pca["labels"],
                  "window": [hist.index[0].date().isoformat(), hist.index[-1].date().isoformat()]}
    hist_ids = ["gsw_nom_02", "gsw_nom_05", "gsw_nom_10", "gsw_nom_30"]
    hh = panel.wide(hist_ids).dropna(how="all")
    out["history"] = {"dates": _dates(hh.index), **{c[-2:] + "y": [None if not np.isfinite(v) else round(float(v), 5)
                                                                for v in hh[c].to_numpy()] for c in hh.columns}}
    nom = panel.wide(["gsw_nom_%02d" % k for k in range(1, 11)]).dropna().iloc[-61:]
    mats10 = np.arange(1, 11, dtype=float)
    decomp = []
    for i in range(1, len(nom)):
        dcmp = fixed_income.return_decomposition(mats10, nom.iloc[i - 1].to_numpy(), nom.iloc[i].to_numpy(), 10.0)
        decomp.append({"date": nom.index[i].date().isoformat(), **{k: round(v, 6) for k, v in dcmp.items()}})
    out["decomposition_10y"] = decomp
    try:
        rd, rm, rz = _curve_on(d, "real")
        out["real"] = {"date": rd, "maturities": rm.tolist(), "zero": rz.tolist()}
        times = np.arange(1, years + 1, dtype=float)
        flows = np.full(years, withdrawal)
        liab = fixed_income.liability_pv_duration(flows, times, rm, rz)
        ladder_dur = float(np.mean(np.arange(1, 11)))
        out["liability"] = {"withdrawal": withdrawal, "years": years, **liab,
                            "duration_gap_vs_10y_tsy": liab["duration"] - fixed_income.macaulay_duration(par.get(10.0, 0.04),
                                                                                                          par.get(10.0, 0.04), 10.0),
                            "duration_gap_vs_10y_ladder": liab["duration"] - ladder_dur,
                            "curve": "GSW TIPS real zero curve (flat beyond 20y)"}
    except (KeyError, IndexError):
        out["real"] = None
        out["liability"] = None
    return out
