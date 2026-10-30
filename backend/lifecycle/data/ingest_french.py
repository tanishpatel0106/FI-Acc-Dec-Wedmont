"""Kenneth French Data Library (public): US market + RF from 1926, developed ex-US and EM markets.

Used when WRDS is unavailable, and always for international history if MSCI is not licensed.
"""
import io
import zipfile

import pandas as pd

from lifecycle.data.http import fetch
from lifecycle.data.schema import finalize_rows

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/Ken.French/ftp/"
FILES = {
    "us3": "F-F_Research_Data_Factors_CSV.zip",
    "us5": "F-F_Research_Data_5_Factors_2x3_CSV.zip",
    "mom": "F-F_Momentum_Factor_CSV.zip",
    "dev": "Developed_ex_US_3_Factors_CSV.zip",
    "em": "Emerging_5_Factors_CSV.zip",
}


def _monthly_table(zip_name: str) -> pd.DataFrame:
    path = fetch(BASE + zip_name, zip_name)
    with zipfile.ZipFile(path) as zf:
        inner = zf.namelist()[0]
        text = zf.read(inner).decode("latin-1")
    lines = text.splitlines()
    header = None
    rows = []
    for i in range(len(lines)):
        parts = [p.strip() for p in lines[i].split(",")]
        if header is None:
            if len(parts) > 1 and parts[0] == "" and parts[1] != "":
                header = parts[1:]
            continue
        if len(parts[0]) == 6 and parts[0].isdigit():
            rows.append(parts)
            continue
        if len(rows) > 0:
            break  # end of the monthly block (annual block follows)
    if header is None or len(rows) == 0:
        raise RuntimeError("could not parse French file " + zip_name)
    index = pd.to_datetime([r[0] for r in rows], format="%Y%m") + pd.offsets.MonthEnd(0)
    data = {}
    for j in range(len(header)):
        data[header[j]] = pd.to_numeric([r[j + 1] for r in rows], errors="coerce") / 100.0
    frame = pd.DataFrame(data, index=index)
    # French uses -99.99 / -999 as missing
    frame = frame.mask(frame <= -0.99)
    return frame


def pull_french() -> pd.DataFrame:
    rows = []
    us = _monthly_table(FILES["us3"])
    for ts in us.index:
        mkt = us.loc[ts, "Mkt-RF"]
        rf = us.loc[ts, "RF"]
        if pd.isna(mkt) or pd.isna(rf):
            continue
        rows.append({"month_end": ts, "series_id": "us_eq", "value": float(mkt + rf), "quantity": "total_return",
                     "provenance": "index_derived", "source": "french:F-F_Research_Data_Factors.Mkt-RF+RF"})
        rows.append({"month_end": ts, "series_id": "tbill", "value": float(rf), "quantity": "total_return",
                     "provenance": "observed", "source": "french:F-F_Research_Data_Factors.RF"})
        for col, sid in [("Mkt-RF", "ff_mktrf"), ("SMB", "ff_smb"), ("HML", "ff_hml"), ("RF", "ff_rf")]:
            v = us.loc[ts, col]
            if not pd.isna(v):
                rows.append({"month_end": ts, "series_id": sid, "value": float(v), "quantity": "total_return",
                             "provenance": "index_derived", "source": "french:F-F_Research_Data_Factors." + col})
    for key, cols in [("us5", [("RMW", "ff_rmw"), ("CMA", "ff_cma")]), ("mom", [(None, "ff_umd")])]:
        try:
            table = _monthly_table(FILES[key])
        except Exception as exc:
            print("warning: French", key, "failed:", exc)
            continue
        for col, sid in cols:
            name = col if col is not None else table.columns[0]
            for ts, v in table[name].dropna().items():
                rows.append({"month_end": ts, "series_id": sid, "value": float(v), "quantity": "total_return",
                             "provenance": "index_derived", "source": "french:" + FILES[key] + "." + name})
    for key, sid in [("dev", "intl_eq"), ("em", "em_eq")]:
        try:
            table = _monthly_table(FILES[key])
        except Exception as exc:
            print("warning: French", key, "failed:", exc)
            continue
        for ts in table.index:
            mkt = table.loc[ts, "Mkt-RF"]
            rf = table.loc[ts, "RF"]
            if pd.isna(mkt) or pd.isna(rf):
                continue
            rows.append({"month_end": ts, "series_id": sid, "value": float(mkt + rf), "quantity": "total_return",
                         "provenance": "index_derived", "source": "french:" + FILES[key] + ".Mkt-RF+RF"})
    return finalize_rows(rows)


def read_french_bytes(data: bytes) -> pd.DataFrame:  # pragma: no cover - helper for notebooks
    return pd.read_csv(io.BytesIO(data))
