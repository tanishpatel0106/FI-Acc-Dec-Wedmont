"""Page H: generator diagnostics, dependence, stress library and sequence-risk timing (brief section 5)."""
from typing import Any

import numpy as np
from pydantic import Field
from scipy import stats

from lifecycle.data import panel
from lifecycle.engine.scenarios.base import ScenarioTensor
from lifecycle.studies import common as S

STRESSES = {
    # name: (description, months, additive monthly shocks by asset class: equity, nominal bond per duration-year, cash, inflation)
    "rate_shock_+200bp": ("Parallel +200bp nominal yield shock over 12 months", 12, 0.0, 0.02, 0.0, 0.0),
    "inflation_shock": ("Cumulative +10% CPI over 24 months (real erosion of nominal assets)", 24, 0.0, 0.0, 0.0, 0.10),
    "equity_drawdown_-35": ("Equity -35% over 12 months", 12, -0.35, 0.0, 0.0, 0.0),
    "2022_like": ("Equity -20% and +250bp yields over 12 months (positive stock-bond correlation)", 12, -0.20, 0.025,
                  0.0, 0.05),
    "stagflation": ("Equity -25%, +150bp yields, +8% CPI over 24 months", 24, -0.25, 0.015, 0.0, 0.08),
    "recession_rally": ("Equity -35% with -150bp yields (bond rally) over 12 months", 12, -0.35, -0.015, 0.0, -0.01),
}
STRESS_NOTE = ("Synthetic, model-generated counterfactual shocks layered on matched bootstrap paths; they are not "
               "historical observations. Bond shocks use -modified duration x dy; inflation shocks reduce the real "
               "return of every nominal asset by the extra monthly CPI.")


class ScenarioLabSpec(S.Frozen):
    data: S.StudyData = Field(default_factory=lambda: S.StudyData(universe="core_duration"))
    scenario: S.StudyScenario = Field(default_factory=lambda: S.StudyScenario(n_paths=2000))
    investor: S.StudyInvestor = Field(default_factory=lambda: S.StudyInvestor(horizon_years=30))
    preferences: S.StudyPrefs = Field(default_factory=S.StudyPrefs)
    generators: tuple[str, ...] = ("historical", "bootstrap", "student_t", "markov_switching", "curve_factor")
    n_paths_per_generator: int = Field(1000, ge=100, le=10000)
    withdrawal: float = 0.04
    portfolios: dict[str, dict[str, float]] = Field(default_factory=lambda: {
        "100/0": {"us_eq": 1.0}, "60/40": {"us_eq": 0.6, "ust_10y": 0.4}, "40/60": {"us_eq": 0.4, "ust_10y": 0.6},
        "PP ex-gold": {"us_eq": 0.25, "ust_30y": 0.25, "tbill": 0.5},
        "60/30/10 cash": {"us_eq": 0.6, "ust_10y": 0.3, "tbill": 0.1}})
    stresses: tuple[str, ...] = tuple(STRESSES)
    shock_timing_years: tuple[int, ...] = (0, 5, 10, 20)
    cohort_years: int = 30
    label: str | None = None


def _monthly_stats(x: np.ndarray) -> dict[str, float]:
    return {"mean_annual": float(x.mean() * 12), "vol_annual": float(x.std() * np.sqrt(12)),
            "skew": float(stats.skew(x)), "kurtosis": float(stats.kurtosis(x, fisher=False)),
            "q01": float(np.quantile(x, 0.01)), "q05": float(np.quantile(x, 0.05)), "q95": float(np.quantile(x, 0.95))}


def _acf_sq(x: np.ndarray, lag: int = 1) -> float:
    z = (x - x.mean()) ** 2
    return float(np.corrcoef(z[:-lag], z[lag:])[0, 1])


def _roll12(x: np.ndarray) -> np.ndarray:
    lg = np.log1p(x)
    c = np.cumsum(np.concatenate([[0], lg]))
    return np.expm1(c[12:] - c[:-12])


def _joint_down(eq12: np.ndarray, bd12: np.ndarray, eq_th, bd_th) -> list[list[float]]:
    return [[float(np.mean((eq12 <= a) & (bd12 <= b))) for b in bd_th] for a in eq_th]


def apply_stress(ten: ScenarioTensor, name: str, start_month: int, durations: dict[str, float]) -> ScenarioTensor:
    desc, months, eq, dy, cash, infl = STRESSES[name]
    R = ten.real_returns.copy()
    end = min(start_month + months, ten.n_months)
    m = end - start_month
    if m <= 0:
        return ten
    for i, a in enumerate(ten.assets):
        shock = 0.0
        if a in ("us_eq", "intl_eq", "em_eq", "reit"):
            shock += np.expm1(np.log1p(eq) / months) if eq != 0 else 0.0
        if a.startswith("ust_") or a in ("ig_credit",):
            shock += -durations.get(a, 0.0) * dy / months
        if a != "tips" and infl != 0:
            shock += -infl / months
        R[:, start_month:end, i] = (1 + R[:, start_month:end, i]) * (1 + shock) - 1
    R = np.maximum(R, -0.95)
    return ScenarioTensor(ten.assets, R, ten.inflation, ten.regime, ten.n_regimes, dict(ten.meta), ten.decision)


def _durations(assets) -> dict[str, float]:
    from lifecycle.engine import fixed_income

    out = {}
    try:
        w = panel.wide(["gsw_nom_%02d" % m for m in range(1, 31)]).dropna()
        row = w.iloc[-1]
        cm = np.array([int(c[-2:]) for c in row.index], float)
        cz = row.to_numpy()
    except Exception:
        cm = cz = None
    for a in assets:
        if a.startswith("ust_"):
            mt = float(a.split("_")[1][:-1])
            y = float(np.interp(mt, cm, cz)) if cm is not None else 0.04
            out[a] = fixed_income.modified_duration(y, y, mt)
        elif a == "ig_credit":
            out[a] = 7.0
    return out


def run_scenario_lab(spec: ScenarioLabSpec, progress: S.Progress) -> dict[str, Any]:
    u = S.universe_or_raise(spec.data)
    assets = u.assets
    hist = u.real.to_numpy()
    eq_i = assets.index("us_eq")
    bd = "ust_10y" if "ust_10y" in assets else assets[2]
    bd_i = assets.index(bd)
    eq12 = _roll12(hist[:, eq_i])
    bd12 = _roll12(hist[:, bd_i])
    eq_th = [-0.10, -0.20, -0.30]
    bd_th = [0.0, -0.05, -0.10]
    half = len(hist) // 2
    gens = []
    dist = {"assets": list(assets), "quantile_levels": np.linspace(0.01, 0.99, 50).round(3).tolist(), "hist": {},
            "generators": {}}
    for i, a in enumerate(assets):
        dist["hist"][a] = {"quantiles": np.quantile(hist[:, i], dist["quantile_levels"]).tolist(),
                           "hist_counts": np.histogram(hist[:, i], bins=40, range=(-0.25, 0.25))[0].tolist(),
                           **_monthly_stats(hist[:, i])}
    dist["bins"] = np.linspace(-0.25, 0.25, 41).tolist()
    joint = {"eq_thresholds": eq_th, "bond_thresholds": bd_th, "bond": bd,
             "observed": _joint_down(eq12, bd12, eq_th, bd_th),
             "observed_first_half": _joint_down(eq12[:half], bd12[:half], eq_th, bd_th),
             "observed_second_half": _joint_down(eq12[half:], bd12[half:], eq_th, bd_th), "modeled": {}}
    fans: dict[str, Any] = {}
    pit: dict[str, Any] = {}
    tens: dict[str, ScenarioTensor] = {}
    w6040 = S.weights_vector({"us_eq": 0.6, bd: 0.4}, assets)
    for gi, g in enumerate(spec.generators):
        progress("fitting " + g, 0.02 + 0.4 * gi / len(spec.generators))
        row: dict[str, Any] = {"generator": g}
        try:
            n = spec.n_paths_per_generator
            es = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences, generator=g, n_paths=n)
            ten = S.get_tensor(es)
            ctx = S.get_context(es, ten, es.scenario.seed)
            tens[g] = ten
            R = ten.real_returns
            flat = R.reshape(-1, R.shape[2])
            row.update({"training_window": [u.start.date().isoformat(), u.end.date().isoformat()], "n_paths": ten.n_paths,
                        "months": ten.n_months, "model": ten.meta.get("model", {})})
            sim_corr = float(np.corrcoef(flat[:, eq_i], flat[:, bd_i])[0, 1])
            hist_corr = float(np.corrcoef(hist[:, eq_i], hist[:, bd_i])[0, 1])
            s_eq = _monthly_stats(flat[:, eq_i])
            h_eq = _monthly_stats(hist[:, eq_i])
            clip = float(np.mean(flat <= -0.9499))
            sub = R[: min(200, R.shape[0])]
            e12 = np.concatenate([_roll12(p[:, eq_i]) for p in sub])
            b12 = np.concatenate([_roll12(p[:, bd_i]) for p in sub])
            joint["modeled"][g] = _joint_down(e12, b12, eq_th, bd_th)
            acf_sim = float(np.nanmean([_acf_sq(p[:, eq_i]) for p in sub]))
            checks = {"mean": abs(s_eq["mean_annual"] - h_eq["mean_annual"]) < 2 * h_eq["vol_annual"] / np.sqrt(len(hist) / 12),
                      "vol": abs(s_eq["vol_annual"] / h_eq["vol_annual"] - 1) < 0.15,
                      "tail_q01": abs(s_eq["q01"] - h_eq["q01"]) < 0.03,
                      "eq_bond_corr": abs(sim_corr - hist_corr) < 0.15, "clipping": clip < 0.001}
            row.update({"equity_sim": s_eq, "equity_hist": h_eq, "corr_eq_bond_sim": sim_corr,
                        "corr_eq_bond_hist": hist_corr, "acf_sq_sim": acf_sim, "acf_sq_hist": _acf_sq(hist[:, eq_i]),
                        "clipped_share": clip, "checks": checks,
                        "verdict": "pass" if all(checks.values()) else ("caution" if sum(checks.values()) >= 3 else "fail")})
            dist["generators"][g] = {a: {"quantiles": np.quantile(flat[:, i], dist["quantile_levels"]).tolist(),
                                         "hist_counts": np.histogram(flat[:, i], bins=40, range=(-0.25, 0.25))[0].tolist()}
                                     for i, a in enumerate(assets)}
            # PIT of historical returns under the simulated marginal (uniform if the marginal fits)
            pits = {}
            for i, a in enumerate(assets[:3]):
                srt = np.sort(flat[:, i])
                pv = np.searchsorted(srt, hist[:, i]) / len(srt)
                cnt = np.histogram(pv, bins=10, range=(0, 1))[0]
                chi = stats.chisquare(cnt)
                pits[a] = {"counts": cnt.tolist(), "chi2": float(chi.statistic), "p": float(chi.pvalue),
                           "flag": bool(chi.pvalue < 0.01)}
            pit[g] = pits
            o = S.run(ctx, w6040, S.strategy("calendar_12m"), rate=spec.withdrawal, record=True)
            fans[g] = {"wealth": S.fan(o.wealth_y), "consumption": S.fan(o.cons_y),
                       "sample_wealth": S.to_list(o.wealth_y[:12], 0),
                       "success": float(S.success(o.first_shortfall, spec.investor.horizon_years * 12).mean())}
        except Exception as exc:
            row.update({"error": str(exc)[:300], "verdict": "fail"})
        gens.append(row)

    # SC-04 OOS: model fitted on the first half, evaluated on the second half
    try:
        d1 = spec.data.model_copy(update={"calibration_end": u.real.index[half].date().isoformat()})
        es1 = S.experiment_spec(d1, spec.scenario, spec.investor, spec.preferences, generator="bootstrap", n_paths=300)
        t1 = S.get_tensor(es1)
        e12 = np.concatenate([_roll12(p[:, eq_i]) for p in t1.real_returns])
        b12 = np.concatenate([_roll12(p[:, bd_i]) for p in t1.real_returns])
        joint["oos_first_half_model"] = _joint_down(e12, b12, eq_th, bd_th)
        joint["oos_split"] = u.real.index[half].date().isoformat()
    except Exception as exc:
        joint["oos_error"] = str(exc)

    # SC-05 / SC-06 / SC-07: dependence and regimes from the shared analytics (derived only)
    progress("dependence", 0.5)
    from lifecycle import analytics

    try:
        dep = analytics.dependence_view(u.name, "us_eq", bd, None, None)
    except Exception as exc:
        dep = {"error": str(exc)}
    try:
        reg = analytics.regimes_view(u.name, 2, None, None)
        filt = np.array(reg["filtered"])
        reg_summary = {"transition": reg["transition"], "expected_duration_months": reg["expected_duration_months"],
                       "names": reg["names"], "mu_annual": reg["mu_annual"], "vol_annual": reg["vol_annual"],
                       "stationary": reg["stationary"], "bic": reg["bic"],
                       "mean_max_filtered_prob": float(filt.max(axis=1).mean()),
                       "share_uncertain_months": float(np.mean(filt.max(axis=1) < 0.8)),
                       "dates": reg["dates"], "filtered": reg["filtered"], "series": reg["series"]}
    except Exception as exc:
        reg_summary = {"error": str(exc)}
    x = u.nominal["us_eq"].to_numpy()
    y = u.nominal[bd].to_numpy()
    tails = []
    for q in (0.05, 0.10):
        qx, qy = np.quantile(x, q), np.quantile(y, q)
        both = int(np.sum((x <= qx) & (y <= qy)))
        tails.append({"q": q, "joint_exceedances": both, "expected_independent": float(len(x) * q * q),
                      "n": int(len(x)), "threshold_eq": float(qx), "threshold_bond": float(qy)})
    copula = {"t_copula": dep.get("t_copula"), "empirical_tails": tails}

    # SC-08 inflation vs yield change vs bond return (annual, non-overlapping)
    infl = u.inflation.to_numpy()
    try:
        y10 = panel.series("y_dgs10").reindex(u.real.index).to_numpy()
    except KeyError:
        y10 = np.full(len(infl), np.nan)
    idx = list(range(12, len(infl), 12))
    scat = {"dates": [u.real.index[i].date().isoformat() for i in idx],
            "cpi_yoy": [float(np.prod(1 + infl[i - 12:i]) - 1) for i in idx],
            "d_yield_10y": [float(y10[i] - y10[i - 12]) if np.isfinite(y10[i]) and np.isfinite(y10[i - 12]) else None
                            for i in idx],
            "bond_return_nominal": [float(np.prod(1 + u.nominal[bd].to_numpy()[i - 12:i]) - 1) for i in idx],
            "breakpoints": dep.get("change_points", {}).get("dates", []) if isinstance(dep, dict) else []}

    # SC-09 stress matrix and SC-10 shock timing on matched bootstrap paths
    progress("stress", 0.65)
    es = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences, generator="bootstrap",
                           n_paths=spec.n_paths_per_generator)
    ten = S.get_tensor(es)
    ctx = S.get_context(es, ten, es.scenario.seed)
    durs = _durations(assets)
    ports = {}
    for pn, pw in spec.portfolios.items():
        try:
            ports[pn] = S.weights_vector(pw, assets)
        except S.IncompatibleUniverse:
            continue
    mh = spec.investor.horizon_years * 12
    base_out = {pn: S.run(ctx, w, S.strategy("calendar_12m"), rate=spec.withdrawal) for pn, w in ports.items()}
    matrix = {"stresses": list(spec.stresses), "descriptions": {k: STRESSES[k][0] for k in spec.stresses},
              "portfolios": list(ports), "d_ce": [], "d_fail": [], "note": STRESS_NOTE}
    for sname in spec.stresses:
        st = apply_stress(ten, sname, 0, durs)
        rce, rf = [], []
        for pn, w in ports.items():
            o = S.run(ctx, w, S.strategy("calendar_12m"), rate=spec.withdrawal, tensor=st)
            rce.append(S.delta_block(o, base_out[pn], spec.preferences.gamma, n_boot=0)["delta"])
            rf.append(float(S.success(base_out[pn].first_shortfall, mh).mean() - S.success(o.first_shortfall, mh).mean()))
        matrix["d_ce"].append(rce)
        matrix["d_fail"].append(rf)
    progress("sequence timing", 0.8)
    timing = {"shock": "equity_drawdown_-35", "years": list(spec.shock_timing_years), "portfolios": {}}
    for pn in ("60/40", "100/0"):
        if pn not in ports:
            continue
        rows = []
        for yv in spec.shock_timing_years:
            st = apply_stress(ten, "equity_drawdown_-35", yv * 12, durs)
            o = S.run(ctx, ports[pn], S.strategy("calendar_12m"), rate=spec.withdrawal, tensor=st, record=True)
            rows.append({"year": yv, "success": float(S.success(o.first_shortfall, mh).mean()),
                         "median_wealth_path": np.round(np.median(o.wealth_y, axis=0), 0).tolist(),
                         "median_funded_path": np.round(np.median(o.cons_y, axis=0), 0).tolist()})
        timing["portfolios"][pn] = rows

    # SC-11 historical cohort start-date map
    progress("cohorts", 0.9)
    cohorts: dict[str, Any] = {"available": False}
    try:
        inv_c = spec.investor.model_copy(update={"horizon_years": spec.cohort_years})
        esh = S.experiment_spec(spec.data, spec.scenario, inv_c, spec.preferences, generator="historical")
        th = S.get_tensor(esh)
        ch = S.get_context(esh, th, esh.scenario.seed)
        from lifecycle.runs import context as C

        starts = list(getattr(C.fitted_model(esh), "last_starts", []))
        cohorts = {"available": True, "starts": starts[: th.n_paths], "years": spec.cohort_years, "portfolios": {},
                   "caveat": "consecutive cohorts overlap by %d of %d years and are not independent" % (
                       spec.cohort_years - 1, spec.cohort_years)}
        for pn, w in ports.items():
            o = S.run(ch, w, S.strategy("calendar_12m"), rate=spec.withdrawal)
            cohorts["portfolios"][pn] = {"success": S.success(o.first_shortfall, spec.cohort_years * 12).tolist(),
                                         "terminal": S.to_list(o.terminal, 0),
                                         "first_shortfall_year": [None if f < 0 else round(f / 12, 2)
                                                                  for f in o.first_shortfall.tolist()]}
    except Exception as exc:
        cohorts = {"available": False, "reason": str(exc)}
    qlike = dep.get("forecast_comparison") if isinstance(dep, dict) else None
    return {"kind": "scenario_lab", "universe": S.universe_block(u), "generators": gens, "distribution": dist,
            "joint_downside": joint, "fans": fans, "pit": pit, "dependence": {k: dep.get(k) for k in (
                "dates", "rolling", "dcc", "full_sample_corr", "change_points", "by_decade")} if isinstance(dep, dict) else {},
            "regimes": reg_summary, "copula": copula, "inflation_scatter": scat, "stress": matrix,
            "shock_timing": timing, "cohorts": cohorts, "qlike": qlike, "warnings": S.common_warnings(u, ten),
            "timings": {}, "summary": {"universe": u.name, "generators": list(spec.generators)}}
