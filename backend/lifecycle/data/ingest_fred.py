"""FRED macro state variables, CMT yields and CPI (public).

Uses the keyless fredgraph CSV endpoint. ALFRED vintages are only needed for macro
signals used inside decision rules; the platform's regime rules use CPI and yields,
whose revisions are negligible, so latest vintages are stored with a publication lag.
"""
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from lifecycle.data.http import complete_months, fetch
from lifecycle.data.schema import finalize_rows

# FRED id -> (series id, quantity, transform, publication lag days)
FRED_SERIES = {
    "CPIAUCNS": ("cpi_nsa", "rate", "pct_change", 15),
    "CPIAUCSL": ("cpi_sa", "rate", "pct_change", 15),
    "GS2": ("y_dgs2", "yield", "pct", 1),
    "GS5": ("y_dgs5", "yield", "pct", 1),
    "GS10": ("y_dgs10", "yield", "pct", 1),
    "GS20": ("y_dgs20", "yield", "pct", 1),
    "GS30": ("y_dgs30", "yield", "pct", 1),
    "FII5": ("y_dfii5", "yield", "pct", 1),
    "FII10": ("y_dfii10", "yield", "pct", 1),
    "T5YIEM": ("y_t5yie", "yield", "pct", 1),
    "T10YIEM": ("y_t10yie", "yield", "pct", 1),
    "TB3MS": ("y_tb3ms", "yield", "pct", 1),
    "AAA": ("y_aaa", "yield", "pct", 1),
    "BAA": ("y_baa", "yield", "pct", 1),
    "UNRATE": ("s_unrate", "rate", "pct", 7),
    "INDPRO": ("s_indpro", "index_level", "level", 16),
    "USREC": ("s_usrec", "rate", "level", 365),
    "VIXCLS": ("s_vixcls", "index_level", "level_monthly_last", 0),
}


def _read_fred_csv(fred_id: str) -> pd.Series:
    key = os.environ.get("FRED_API_KEY", "")
    if key != "":
        # the official API is faster and more reliable than the keyless fredgraph endpoint
        url = ("https://api.stlouisfed.org/fred/series/observations?file_type=json&series_id=" + fred_id +
               "&api_key=" + key)
        path = fetch(url, "fred_" + fred_id + ".json")
        obs = json.loads(path.read_text())["observations"]
        idx = pd.to_datetime([o["date"] for o in obs])
        values = pd.to_numeric(pd.Series([o["value"] for o in obs]), errors="coerce")
        return pd.Series(values.values, index=idx, name=fred_id).dropna()
    path = fetch("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + fred_id, "fred_" + fred_id + ".csv")
    frame = pd.read_csv(io.StringIO(path.read_text()))
    date_col = frame.columns[0]
    frame[date_col] = pd.to_datetime(frame[date_col])
    values = pd.to_numeric(frame[fred_id], errors="coerce")
    return pd.Series(values.values, index=frame[date_col], name=fred_id).dropna()


def _download_all(series: list[str]) -> dict[str, pd.Series | Exception]:
    """Fetch every FRED series concurrently (a handful of workers keeps within FRED's rate limits)."""
    out: dict[str, pd.Series | Exception] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_read_fred_csv, fid): fid for fid in series}
        for fut in as_completed(futures):
            fid = futures[fut]
            try:
                out[fid] = fut.result()
            except Exception as exc:
                out[fid] = exc
    return out


def pull_fred(series: list[str] | None = None) -> pd.DataFrame:
    if series is None:
        series = list(FRED_SERIES.keys())
    rows = []
    downloaded = _download_all(series)
    for fred_id in series:
        sid, quantity, transform, lag = FRED_SERIES[fred_id]
        raw = downloaded[fred_id]
        if isinstance(raw, Exception):  # network or parsing failure is reported, never silenced into data
            print("warning: FRED", fred_id, "failed:", raw)
            continue
        if transform == "level_monthly_last":
            cutoff = complete_months(raw.index)
            raw = raw.resample("ME").last().dropna()
            raw = raw[raw.index <= cutoff]
        idx = raw.index + pd.offsets.MonthEnd(0)
        values = raw.values.astype(float)
        if transform == "pct":
            values = values / 100.0
        if transform == "pct_change":
            out = []
            for i in range(1, len(values)):
                # skip months that are not consecutive (gaps are recorded, not bridged)
                if (idx[i].to_period("M") - idx[i - 1].to_period("M")).n != 1:
                    continue
                out.append((idx[i], values[i] / values[i - 1] - 1.0))
        else:
            out = [(idx[i], values[i]) for i in range(len(values))]
        for month_end, v in out:
            rows.append({"month_end": month_end, "series_id": sid, "value": float(v), "quantity": quantity,
                         "provenance": "observed", "source": "fred:" + fred_id,
                         "available_from": month_end + pd.Timedelta(days=lag)})
    return finalize_rows(rows)
