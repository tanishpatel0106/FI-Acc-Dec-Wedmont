"""NY Fed ACM term premia and expected short-rate components (10Y)."""
import pandas as pd

from lifecycle.data.http import complete_months, fetch
from lifecycle.data.schema import finalize_rows

URL = "https://www.newyorkfed.org/medialibrary/media/research/data_indicators/ACMTermPremium.xls"


def pull_acm() -> pd.DataFrame:
    path = fetch(URL, "acm_term_premium.xls")
    frame = None
    for sheet in ["ACM Monthly", 0]:
        try:
            frame = pd.read_excel(path, sheet_name=sheet)
            break
        except Exception:
            continue
    if frame is None:
        raise RuntimeError("could not parse ACM workbook")
    date_col = frame.columns[0]
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce", format="mixed")
    frame = frame.dropna(subset=[date_col]).set_index(date_col).sort_index()
    monthly = frame.resample("ME").last()
    monthly = monthly[monthly.index <= complete_months(frame.index)]
    rows = []
    for col, sid in [("ACMTP10", "s_acm_tp10"), ("ACMRNY10", "s_acm_rny10")]:
        if col not in monthly.columns:
            print("warning: ACM column missing", col)
            continue
        for ts, v in monthly[col].dropna().items():
            rows.append({"month_end": ts, "series_id": sid, "value": float(v) / 100.0, "quantity": "yield",
                         "provenance": "model_generated", "source": "nyfed:acm." + col})
    return finalize_rows(rows)
