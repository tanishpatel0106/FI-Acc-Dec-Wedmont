"""Fama-French factors from WRDS (ff.factors_monthly, ff.fivefactors_monthly)."""
import pandas as pd

from lifecycle.data import wrds_client
from lifecycle.data.schema import finalize_rows


def pull_ff(start_date: str = "1926-01-01", end_date: str = "2100-01-01") -> pd.DataFrame:
    db = wrds_client.connect()
    rows = []
    try:
        for table, factors in [("factors_monthly", ["mktrf", "smb", "hml", "rf", "umd"]),
                               ("fivefactors_monthly", ["rmw", "cma"])]:
            if not wrds_client.table_exists(db, "ff", table):
                print("warning: ff." + table + " not in subscription")
                continue
            cols = wrds_client.columns_of(db, "ff", table)
            date_col = wrds_client.pick_column(cols, ["date", "dateff"])
            present = [f for f in factors if f in cols]
            sql = ("select " + date_col + " as d, " + ", ".join(present) + " from ff." + table +
                   " where " + date_col + " between %(s)s and %(e)s order by " + date_col)
            raw = db.raw_sql(sql, params={"s": start_date, "e": end_date}, date_cols=["d"])
            for i in range(len(raw)):
                month_end = raw["d"].iloc[i] + pd.offsets.MonthEnd(0)
                for f in present:
                    v = raw[f].iloc[i]
                    if pd.isna(v):
                        continue
                    rows.append({"month_end": month_end, "series_id": "ff_" + f, "value": float(v),
                                 "quantity": "total_return", "provenance": "observed",
                                 "source": "wrds:ff." + table + "." + f})
    finally:
        wrds_client.release(db)
    return finalize_rows(rows)
