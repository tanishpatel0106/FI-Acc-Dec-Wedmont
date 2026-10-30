"""CRSP fixed-term Treasury indexes (tfz_mth_ft) and risk-free file (tfz_mth_rf)."""
import pandas as pd

from lifecycle.data import wrds_client
from lifecycle.data.schema import finalize_rows

# kytreasnox identifiers of the CRSP fixed-term indexes (verify in the WRDS schema browser)
FT_TERMS = {2000003: "ft_1y", 2000004: "ft_2y", 2000005: "ft_5y", 2000006: "ft_7y", 2000007: "ft_10y",
            2000008: "ft_20y", 2000009: "ft_30y"}
RF_TERMS = {2000001: "rf_1m", 2000002: "rf_3m"}


def _pull(db, table: str, ids: dict[int, str], start_date: str, end_date: str) -> list[dict]:
    library, tname = wrds_client.resolve_table(db, [("crsp", table), ("crsp_a_treasuries", table)])
    cols = wrds_client.columns_of(db, library, tname)
    ret_col = wrds_client.pick_column(cols, ["tmretadj", "tmtotret", "tmret"])
    dur_col = wrds_client.pick_column(cols, ["tmduratn"])
    ytm_col = wrds_client.pick_column(cols, ["tmytm"])
    date_col = wrds_client.pick_column(cols, ["mcaldt", "caldt"])
    if ret_col is None or date_col is None:
        raise RuntimeError("unexpected columns in " + library + "." + tname + ": " + str(cols))
    select = ["kytreasnox", date_col + " as caldt", ret_col + " as ret"]
    if dur_col is not None:
        select.append(dur_col + " as dur")
    if ytm_col is not None:
        select.append(ytm_col + " as ytm")
    id_list = ", ".join(str(k) for k in ids.keys())
    sql = ("select " + ", ".join(select) + " from " + library + "." + tname +
           " where kytreasnox in (" + id_list + ") and " + date_col + " between %(s)s and %(e)s")
    raw = db.raw_sql(sql, params={"s": start_date, "e": end_date}, date_cols=["caldt"])
    rows = []
    src = "wrds:" + library + "." + tname
    for i in range(len(raw)):
        key = int(raw["kytreasnox"].iloc[i])
        if key not in ids:
            continue
        name = ids[key]
        month_end = raw["caldt"].iloc[i] + pd.offsets.MonthEnd(0)
        v = raw["ret"].iloc[i]
        if not pd.isna(v):
            rows.append({"month_end": month_end, "series_id": "crsp_" + name + "_ret", "value": float(v),
                         "quantity": "total_return", "provenance": "observed", "source": src + "." + ret_col})
        if "dur" in raw.columns and not pd.isna(raw["dur"].iloc[i]):
            rows.append({"month_end": month_end, "series_id": "crsp_" + name + "_dur",
                         "value": float(raw["dur"].iloc[i]) / 365.25, "quantity": "rate",
                         "provenance": "observed", "source": src + ".tmduratn"})
        if "ytm" in raw.columns and not pd.isna(raw["ytm"].iloc[i]):
            rows.append({"month_end": month_end, "series_id": "crsp_" + name + "_ytm",
                         "value": float(raw["ytm"].iloc[i]) / 100.0, "quantity": "yield",
                         "provenance": "observed", "source": src + ".tmytm"})
    return rows


def pull_tfz(start_date: str = "1925-12-01", end_date: str = "2100-01-01") -> pd.DataFrame:
    db = wrds_client.connect()
    try:
        rows = _pull(db, "tfz_mth_ft", FT_TERMS, start_date, end_date)
        rows = rows + _pull(db, "tfz_mth_rf", RF_TERMS, start_date, end_date)
    finally:
        wrds_client.release(db)
    return finalize_rows(rows)
