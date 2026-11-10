"""Page G: as-of market-state terminal (latest *available* public observations, not a live ticker).

Everything here is a derived view of the stored panel / daily store, keyed by catalog hash. Observation
dates, publication-lag availability and retrieval vintages are reported separately; a source is flagged
stale relative to today's date when its latest observation is older than its expected cadence.
"""
import json
from datetime import date
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from lifecycle.config import processed_dir, raw_dir
from lifecycle.data import panel
from lifecycle.engine import dependence, fixed_income

SOURCE_GROUPS = {
    "fred": ("FRED (St. Louis Fed)", "public_with_terms", 45),
    "french": ("Ken French Data Library", "public_with_terms", 75),
    "fed": ("Federal Reserve GSW yield curves", "public_open", 75),
    "nyfed": ("NY Fed ACM term premia", "public_open", 75),
    "model": ("Repriced from public yields (model_generated)", "derived", 45),
    "wrds": ("WRDS (institutional entitlement)", "wrds_restricted", 75),
    "synthetic": ("Synthetic test fixture", "test_only", 99999),
}
RELEASE_LAGS = {"cpi_nsa": 15, "cpi_sa": 15, "s_unrate": 7, "s_indpro": 16, "s_usrec": 365, "y_dgs10": 1,
                "y_dfii10": 1, "y_t10yie": 1, "y_baa": 1, "y_aaa": 1, "s_acm_tp10": 30, "s_vixcls": 0}


def _key() -> str:
    return panel.catalog_hash()


def ribbon() -> dict[str, Any]:
    cat = panel.catalog()
    today = pd.Timestamp(date.today())
    rows = []
    for prefix, (label, lic, cadence) in SOURCE_GROUPS.items():
        sub = cat[cat["source"].astype(str).str.startswith(prefix + ":")]
        if len(sub) == 0:
            rows.append({"source": prefix, "label": label, "status": "not ingested", "licence": lic})
            continue
        last = pd.to_datetime(sub["last_obs"]).max()
        vint = pd.to_datetime(sub["vintage"]).max()
        age = int((today - last).days)
        rows.append({"source": prefix, "label": label, "licence": lic, "n_series": int(len(sub)),
                     "latest_observation": last.date().isoformat(), "retrieved_vintage": vint.date().isoformat(),
                     "days_since_observation": age, "stale": age > cadence, "expected_cadence_days": cadence})
    from lifecycle.data.ingest_treasury_daily import latest

    td = latest()
    rows.append({"source": "treasury_daily", "label": "US Treasury daily par curves (official CSV)",
                 "licence": "public_open", "status": "ok" if td["curves"] else "not ingested",
                 "latest_observation": (td["curves"].get("nominal") or {}).get("observation_date"),
                 "retrieved_vintage": td["vintage"], "note": td.get("status")})
    return {"today": today.date().isoformat(), "sources": rows, "panel_built_at": panel.meta().get("built_at"),
            "catalog_hash": _key(), "note": "observation date = period the value describes; vintage = when it was "
                                            "retrieved; neither implies a live market feed"}


def market_view(as_of: str | None = None) -> dict[str, Any]:
    return _market(as_of, _key())


def _last_on_or_before(s: pd.Series, ts: pd.Timestamp) -> tuple[str | None, float | None]:
    s = s.dropna()
    s = s[s.index <= ts]
    if len(s) == 0:
        return None, None
    return s.index[-1].date().isoformat(), float(s.iloc[-1])


@lru_cache(maxsize=32)
def _market(as_of: str | None, ck: str) -> dict[str, Any]:
    p = panel.panel()
    ts = pd.Timestamp(as_of) + pd.offsets.MonthEnd(0) if as_of else pd.to_datetime(p["month_end"]).max()
    out: dict[str, Any] = {"as_of": ts.date().isoformat(), "as_of_rule": "values whose available_from <= as_of "
                                                                         "(publication lags applied)"}
    # point-in-time availability: only rows already published at the as-of date
    pit = p[pd.to_datetime(p["available_from"]) <= ts + pd.Timedelta(days=0)]

    def pit_series(sid):
        sub = pit[pit["series_id"] == sid]
        return pd.Series(sub["value"].to_numpy(), index=pd.DatetimeIndex(sub["month_end"])).sort_index()

    # MS-02 nominal / real curves (GSW zero, monthly) and derived par
    nom = [(m, *_last_on_or_before(pit_series("gsw_nom_%02d" % m), ts)) for m in range(1, 31)]
    nom = [(m, d, v) for m, d, v in nom if v is not None]
    real = [(m, *_last_on_or_before(pit_series("gsw_real_%02d" % m), ts)) for m in range(2, 21)]
    real = [(m, d, v) for m, d, v in real if v is not None]
    curves: dict[str, Any] = {}
    if nom:
        mm = np.array([m for m, _, _ in nom], float)
        zz = np.array([v for _, _, v in nom])
        par = fixed_income.zero_to_par(zz, mm)
        curves["nominal"] = {"basis": "GSW zero (continuously compounded) + derived par", "observation_date": nom[0][1],
                             "maturities": mm.tolist(), "zero": zz.tolist(), "par": [par[k] for k in sorted(par)]}
    if real:
        curves["real"] = {"basis": "GSW TIPS real zero", "observation_date": real[0][1],
                          "maturities": [m for m, _, _ in real], "zero": [v for _, _, v in real]}
    from lifecycle.data.ingest_treasury_daily import latest

    td = latest()
    if td["curves"] and not as_of:
        curves["daily_par"] = td["curves"]
    out["curves"] = curves
    # MS-03 10Y nominal vs real vs breakeven; ACM decomposition
    hist = {}
    for sid in ("y_dgs10", "y_dfii10", "y_t10yie", "s_acm_tp10", "s_acm_rny10", "y_dgs2", "y_baa", "y_aaa", "y_tb3ms"):
        s = pit_series(sid)
        s = s[s.index >= ts - pd.DateOffset(years=25)]
        hist[sid] = {"dates": [d.date().isoformat() for d in s.index], "values": np.round(s.to_numpy(), 6).tolist(),
                     "latest": _last_on_or_before(s, ts)}
    out["series"] = hist
    lat = {k: v["latest"][1] for k, v in hist.items()}
    out["decomposition"] = {"nominal_10y": lat.get("y_dgs10"), "real_10y": lat.get("y_dfii10"),
                            "breakeven_10y": lat.get("y_t10yie"), "acm_term_premium_10y": lat.get("s_acm_tp10"),
                            "acm_expected_short_rate_10y": lat.get("s_acm_rny10"),
                            "note": "ACM term premium + expected short rate is a model decomposition of the ACM fitted "
                                    "yield; CMT nominal - TIPS real = breakeven is a market decomposition including "
                                    "liquidity/inflation risk premia. They are not additive across methodologies."}
    # MS-04 valuation dashboard
    val: dict[str, Any] = {}
    if nom:
        mm = np.array([m for m, _, _ in nom], float)
        zz = np.array([v for _, _, v in nom])
        par = fixed_income.zero_to_par(zz, mm)
        y10 = par.get(10.0)
        y2 = par.get(2.0)
        y5 = par.get(5.0)
        y30 = par.get(30.0)
        if y10 is not None:
            val["duration_10y"] = fixed_income.modified_duration(y10, y10, 10.0)
            roll = (fixed_income.price_on_curve(y10, 9.0 + 11 / 12, mm, zz) /
                    fixed_income.price_on_curve(y10, 10.0, mm, zz) - 1)
            val["roll_down_1m_10y"] = roll
            val["income_per_1m_10y_par"] = 1e6 * y10
        val["slope_2s10s"] = (y10 - y2) if y10 is not None and y2 is not None else None
        val["slope_5s30s"] = (y30 - y5) if y30 is not None and y5 is not None else None
    val["real_yield_10y"] = lat.get("y_dfii10")
    if real:
        rz = np.array([v for _, _, v in real])
        rm = np.array([m for m, _, _ in real], float)
        flows = np.full(30, 40_000.0)
        liab = fixed_income.liability_pv_duration(flows, np.arange(1, 31, dtype=float), rm, rz)
        val["real_income_30y_ladder_per_1m"] = 40_000.0 * 1e6 / liab["pv"]
    val["assumptions"] = "par yields derived from GSW zero curve; roll-down on an unchanged curve; ladder income = "\
                         "level real annuity priced on the TIPS real zero curve (flat beyond 20y)"
    out["valuation"] = val
    # MS-05 rolling correlation with Fisher-z bands
    u = panel.universe_data("core_long_history", None, ts.date().isoformat())
    x = u.nominal["us_eq"].to_numpy()
    y = u.nominal["ust_10y"].to_numpy()
    roll = {}
    for wdw in (12, 36, 60):
        r = dependence.rolling_corr(x, y, wdw)
        z = np.arctanh(np.clip(r, -0.999, 0.999))
        se = 1 / np.sqrt(max(wdw - 3, 1))
        roll[str(wdw)] = {"r": [None if not np.isfinite(v) else round(float(v), 4) for v in r],
                          "lo": [None if not np.isfinite(v) else round(float(np.tanh(v - 1.96 * se)), 4) for v in z],
                          "hi": [None if not np.isfinite(v) else round(float(np.tanh(v + 1.96 * se)), 4) for v in z]}
    dcc = dependence.dcc_garch(np.column_stack([x, y]))
    out["correlation"] = {"dates": [d.date().isoformat() for d in u.real.index], "rolling": roll,
                          "dcc": np.round(dcc["R"][:, 0, 1], 4).tolist(),
                          "warnings": ["Treasury returns are model_generated (repriced from CMT yields)"] +
                          (["latest 12m correlation positive: bonds did not hedge equities"] if roll["12"]["r"][-1]
                           and roll["12"]["r"][-1] > 0 else [])}
    # MS-06 filtered regime probabilities (point-in-time)
    from lifecycle.engine.scenarios.markov_switching import MarkovSwitching

    ms = MarkovSwitching(u.real_array(), u.inflation.to_numpy(), k=2)
    out["regime"] = {"dates": [d.date().isoformat() for d in u.real.index], "filtered": np.round(ms.filtered, 4).tolist(),
                     "names": ms.regime_names(), "latest": ms.filtered[-1].tolist(),
                     "one_step_ahead": (ms.filtered[-1] @ ms.P).tolist(), "model_vintage": {
                         "catalog_hash": _key(), "window": [u.start.date().isoformat(), u.end.date().isoformat()],
                         "k": 2, "loglik": ms.loglik},
                     "note": "filtered (not smoothed) probabilities use only data through each month"}
    # MS-08 release timeline
    rel = []
    for sid, lag in RELEASE_LAGS.items():
        sub = p[p["series_id"] == sid]
        if len(sub) == 0:
            continue
        last = sub.sort_values("month_end").iloc[-1]
        avail_pit = pit[pit["series_id"] == sid]
        rel.append({"series_id": sid, "label": panel.asset_label(sid), "last_period": pd.Timestamp(last["month_end"]).date().isoformat(),
                    "available_from": pd.Timestamp(last["available_from"]).date().isoformat(),
                    "publication_lag_days": lag, "vintage": pd.Timestamp(last["vintage"]).date().isoformat(),
                    "latest_known_at_as_of": pd.Timestamp(avail_pit["month_end"].max()).date().isoformat()
                    if len(avail_pit) else None,
                    "revisions": "latest vintage stored; ALFRED real-time vintages not ingested (revision risk "
                                 "for descriptive use only)" if sid in ("s_indpro", "s_unrate", "cpi_sa") else
                                 "not revised or negligible"})
    out["releases"] = rel
    # MS-09 credit spreads (public FRED Moody's series)
    baa, aaa, g10 = pit_series("y_baa"), pit_series("y_aaa"), pit_series("y_dgs10")
    df = pd.concat([baa.rename("baa"), aaa.rename("aaa"), g10.rename("t10")], axis=1).dropna()
    df = df[df.index <= ts]
    out["credit"] = {"dates": [d.date().isoformat() for d in df.index], "baa_aaa": np.round(df["baa"] - df["aaa"], 5).tolist(),
                     "baa_t10": np.round(df["baa"] - df["t10"], 5).tolist(),
                     "source": "FRED Moody's seasoned Aaa/Baa corporate yields (public); ICE BofA OAS not used "
                               "(restricted 3-year public history)", "licence": "public_with_terms"}
    # MS-11 ETF proxies
    cat = panel.catalog()
    etf = cat[cat["source"].astype(str).str.startswith("wrds:")]
    out["etf_proxies"] = {"available": bool(len(etf)), "series": etf[["series_id", "source", "last_obs"]].to_dict("records")
                          if len(etf) else [], "reason": None if len(etf) else
                          "no WRDS entitlement ingested: ETF proxy returns (CRSP) unavailable in public mode"}
    return out


def refresh_audit() -> dict[str, Any]:
    out: dict[str, Any] = {"ingest_runs": [], "daily_store": []}
    path = processed_dir() / "ingest_audit.json"
    if path.exists():
        out["ingest_runs"] = json.loads(path.read_text())[-20:]
    td = raw_dir() / "treasury_daily"
    if td.exists():
        for v in sorted(td.iterdir()):
            log = v / "refresh_log.json"
            if log.exists():
                out["daily_store"].append({"vintage": v.name, **json.loads(log.read_text())})
    meta = panel.meta()
    out["source_choices"] = meta.get("choices", {})
    cat = panel.catalog()
    out["invalid_series"] = cat[cat["n_missing"] > 0][["series_id", "n_missing", "first_obs", "last_obs"]].to_dict("records")
    out["vintages"] = sorted({str(v) for v in cat["vintage"]})
    return out


def release_pit(series_id: str, as_of: str) -> dict[str, Any]:
    """Historical PIT selector: the latest observation of a series that was published by `as_of`."""
    p = panel.panel()
    sub = p[(p["series_id"] == series_id) & (pd.to_datetime(p["available_from"]) <= pd.Timestamp(as_of))]
    if len(sub) == 0:
        return {"series_id": series_id, "as_of": as_of, "status": "UnavailableAsOf"}
    row = sub.sort_values("month_end").iloc[-1]
    return {"series_id": series_id, "as_of": as_of, "observation_period": pd.Timestamp(row["month_end"]).date().isoformat(),
            "available_from": pd.Timestamp(row["available_from"]).date().isoformat(), "value": float(row["value"])}
