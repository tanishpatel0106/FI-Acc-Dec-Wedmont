"""CRSP monthly market index (crsp.msi legacy / CIZ index series) -> us_eq total and price return."""
import pandas as pd

from lifecycle.data import wrds_client
from lifecycle.data.schema import finalize_rows

CANDIDATES = [("crsp", "msi"), ("crsp_a_indexes", "msi"), ("crsp", "msix")]


def pull_crsp_index(start_date: str = "1925-12-01", end_date: str = "2100-01-01") -> pd.DataFrame:
    db = wrds_client.connect()
    try:
        library, table = wrds_client.resolve_table(db, CANDIDATES)
        cols = wrds_client.columns_of(db, library, table)
        date_col = wrds_client.pick_column(cols, ["date", "caldt", "mthcaldt"])
        if date_col is None:
            raise RuntimeError("no date column in " + library + "." + table)
        wanted = []
        for c in ["vwretd", "vwretx", "ewretd", "totval"]:
            if c in cols:
                wanted.append(c)
            else:
                print("warning: column missing in", library + "." + table, c)
        if "vwretd" not in wanted:
            raise RuntimeError("vwretd missing; cannot build us_eq")
        sql = ("select " + date_col + " as caldt, " + ", ".join(wanted) + " from " + library + "." + table +
               " where " + date_col + " between %(s)s and %(e)s order by " + date_col)
        raw = db.raw_sql(sql, params={"s": start_date, "e": end_date}, date_cols=["caldt"])
    finally:
        wrds_client.release(db)

    src = "wrds:" + library + "." + table
    rows = []
    for i in range(len(raw)):
        month_end = raw["caldt"].iloc[i] + pd.offsets.MonthEnd(0)
        v = raw["vwretd"].iloc[i]
        if not pd.isna(v):
            rows.append({"month_end": month_end, "series_id": "us_eq", "value": float(v),
                         "quantity": "total_return", "provenance": "observed", "source": src + ".vwretd"})
        if "vwretx" in wanted:
            v = raw["vwretx"].iloc[i]
            if not pd.isna(v):
                rows.append({"month_end": month_end, "series_id": "us_eq_price", "value": float(v),
                             "quantity": "price_return", "provenance": "observed", "source": src + ".vwretx"})
    return finalize_rows(rows)
