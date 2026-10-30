"""Federal Reserve GSW fitted nominal (1961-) and TIPS real (1999-) zero-coupon curves.

Stores month-end continuously-compounded zero yields at annual maturities, which is
what the PCA and the curve-factor scenario model consume.
"""
import io

import numpy as np
import pandas as pd

from lifecycle.data.http import fetch
from lifecycle.data.schema import finalize_rows

NOMINAL_URL = "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv"
REAL_URL = "https://www.federalreserve.gov/data/yield-curve-tables/feds200805.csv"


def _read_fed_csv(url: str, name: str) -> pd.DataFrame:
    path = fetch(url, name)
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    start = 0
    for i in range(len(lines)):
        if lines[i].startswith("Date,"):
            start = i
            break
    frame = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame = frame.dropna(subset=["Date"]).set_index("Date").sort_index()
    return frame.apply(pd.to_numeric, errors="coerce")


def pull_gsw() -> pd.DataFrame:
    rows = []
    nominal = _read_fed_csv(NOMINAL_URL, "gsw_nominal.csv")
    month_end = nominal.resample("ME").last()
    for m in range(1, 31):
        col = "SVENY%02d" % m
        if col not in month_end.columns:
            continue
        series = month_end[col].dropna()
        for ts, v in series.items():
            rows.append({"month_end": ts, "series_id": "gsw_nom_%02d" % m, "value": float(v) / 100.0,
                         "quantity": "yield", "provenance": "model_generated",
                         "source": "fed:gsw_nominal." + col})
    try:
        real = _read_fed_csv(REAL_URL, "gsw_real.csv")
        month_end_r = real.resample("ME").last()
        for m in range(2, 21):
            col = "TIPSY%02d" % m
            if col not in month_end_r.columns:
                continue
            series = month_end_r[col].dropna()
            for ts, v in series.items():
                if not np.isfinite(v):
                    continue
                rows.append({"month_end": ts, "series_id": "gsw_real_%02d" % m, "value": float(v) / 100.0,
                             "quantity": "yield", "provenance": "model_generated",
                             "source": "fed:gsw_tips." + col})
    except Exception as exc:
        print("warning: GSW TIPS curve failed:", exc)
    return finalize_rows(rows)
