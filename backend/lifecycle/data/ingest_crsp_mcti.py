"""CRSP Treasury & inflation indexes (crsp.mcti): duration ladder, bills and CPI."""
import pandas as pd

from lifecycle.data import wrds_client
from lifecycle.data.schema import finalize_rows

MCTI_COLUMNS = ["b1ret", "b2ret", "b5ret", "b7ret", "b10ret",
                "b20ret", "b30ret", "t30ret", "t90ret", "cpiret"]

# canonical ids for the columns that feed the universes; others are kept under crsp_mcti_*
CANONICAL = {"b2ret": "ust_2y", "b5ret": "ust_5y", "b10ret": "ust_10y", "b20ret": "ust_20y",
             "b30ret": "ust_30y", "t30ret": "tbill", "cpiret": "cpi_nsa"}


def pull_mcti(start_date: str = "1925-12-01", end_date: str = "2100-01-01") -> pd.DataFrame:
    db = wrds_client.connect()
    try:
        library, table = wrds_client.resolve_table(db, [("crsp", "mcti"), ("crsp_a_treasuries", "mcti")])
        available = wrds_client.columns_of(db, library, table)
        present = []
        for i in range(len(MCTI_COLUMNS)):
            if MCTI_COLUMNS[i] in available:
                present.append(MCTI_COLUMNS[i])
            else:
                print("warning: column missing in crsp.mcti:", MCTI_COLUMNS[i])
        if len(present) == 0:
            raise RuntimeError("crsp.mcti returned none of the expected columns")
        sql = ("select caldt, " + ", ".join(present) + " from " + library + "." + table +
               " where caldt between %(s)s and %(e)s order by caldt")
        raw = db.raw_sql(sql, params={"s": start_date, "e": end_date}, date_cols=["caldt"])
    finally:
        wrds_client.release(db)

    rows = []
    for i in range(len(raw)):
        month_end = raw["caldt"].iloc[i] + pd.offsets.MonthEnd(0)
        for j in range(len(present)):
            col = present[j]
            value = raw[col].iloc[i]
            if pd.isna(value):
                continue  # gaps are recorded by the catalog, never filled
            series_id = CANONICAL.get(col, "crsp_mcti_" + col)
            quantity = "rate" if col == "cpiret" else "total_return"
            rows.append({"month_end": month_end,
                         "series_id": series_id,
                         "value": float(value),
                         "quantity": quantity,
                         "provenance": "observed",
                         "source": "wrds:crsp.mcti." + col})
    # CPI is published mid-following-month
    return finalize_rows(rows, publication_lag_days=15)
