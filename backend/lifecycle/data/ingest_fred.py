"""FRED macro state variables, CMT yields and CPI (public).

Uses the keyless fredgraph CSV endpoint. ALFRED vintages are only needed for macro
signals used inside decision rules; the platform's regime rules use CPI and yields,
whose revisions are negligible, so latest vintages are stored with a publication lag.
"""
import io

import pandas as pd

from lifecycle.data.http import fetch
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
    path = fetch("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + fred_id, "fred_" + fred_id + ".csv")
    frame = pd.read_csv(io.StringIO(path.read_text()))
    date_col = frame.columns[0]
    frame[date_col] = pd.to_datetime(frame[date_col])
    values = pd.to_numeric(frame[fred_id], errors="coerce")
    return pd.Series(values.values, index=frame[date_col], name=fred_id).dropna()


def pull_fred(series: list[str] | None = None) -> pd.DataFrame:
    if series is None:
        series = list(FRED_SERIES.keys())
    rows = []
    for fred_id in series:
        sid, quantity, transform, lag = FRED_SERIES[fred_id]
        try:
            raw = _read_fred_csv(fred_id)
        except Exception as exc:  # network or parsing failure is reported, never silenced into data
            print("warning: FRED", fred_id, "failed:", exc)
            continue
        if transform == "level_monthly_last":
            raw = raw.resample("ME").last().dropna()
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
