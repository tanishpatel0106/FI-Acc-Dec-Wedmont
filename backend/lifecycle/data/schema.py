"""Canonical monthly panel contract (brief section 3.4)."""
from datetime import date

import pandas as pd

PANEL_COLUMNS = ["month_end", "series_id", "value", "quantity", "provenance", "source", "vintage",
                 "available_from"]

QUANTITIES = ("total_return", "price_return", "yield", "index_level", "rate")
PROVENANCES = ("observed", "index_derived", "model_generated")

# source priority when the same canonical series is available from several sources
PROVENANCE_RANK = {"observed": 0, "index_derived": 1, "model_generated": 2}


def empty_panel() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in PANEL_COLUMNS})


def finalize_rows(rows: list[dict], vintage: date | None = None, publication_lag_days: int = 0) -> pd.DataFrame:
    """Turn ingestion rows into a panel frame with explicit types and checks."""
    if vintage is None:
        vintage = date.today()
    frame = pd.DataFrame(rows)
    if len(frame) == 0:
        return empty_panel()
    for col in ["month_end", "series_id", "value", "quantity", "provenance", "source"]:
        if col not in frame.columns:
            raise ValueError("ingestion row missing column: " + col)
    frame["month_end"] = pd.to_datetime(frame["month_end"]) + pd.offsets.MonthEnd(0)
    frame["value"] = frame["value"].astype("float64")
    bad_q = set(frame["quantity"].unique()) - set(QUANTITIES)
    if len(bad_q) > 0:
        raise ValueError("unknown quantity values: " + str(bad_q))
    bad_p = set(frame["provenance"].unique()) - set(PROVENANCES)
    if len(bad_p) > 0:
        raise ValueError("unknown provenance values: " + str(bad_p))
    if "vintage" not in frame.columns:
        frame["vintage"] = pd.Timestamp(vintage)
    if "available_from" not in frame.columns:
        frame["available_from"] = frame["month_end"] + pd.Timedelta(days=publication_lag_days)
    frame["vintage"] = pd.to_datetime(frame["vintage"])
    frame["available_from"] = pd.to_datetime(frame["available_from"])
    dup = frame.duplicated(subset=["month_end", "series_id", "source"])
    if dup.any():
        raise ValueError("duplicate (month_end, series_id, source) rows: " + str(int(dup.sum())))
    return frame[PANEL_COLUMNS].sort_values(["series_id", "month_end"]).reset_index(drop=True)
