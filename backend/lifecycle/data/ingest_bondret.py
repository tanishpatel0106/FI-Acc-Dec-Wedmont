"""WRDS Bond Returns (TRACE-based) -> value-weighted IG and HY credit indexes.

Aggregation runs server-side so bond-level observations never leave WRDS.
Weights are previous-month amount outstanding; rating_num 1..10 is AAA..BBB-.
"""
import pandas as pd

from lifecycle.data import wrds_client
from lifecycle.data.schema import finalize_rows

CANDIDATES = [("wrdsapps_bondret", "bondret"), ("wrdsapps", "bondret")]


def pull_bondret(start_date: str = "2002-07-01", end_date: str = "2100-01-01") -> pd.DataFrame:
    db = wrds_client.connect()
    try:
        library, table = wrds_client.resolve_table(db, CANDIDATES)
        cols = wrds_client.columns_of(db, library, table)
        for needed in ["date", "cusip", "ret_eom", "rating_num", "amount_outstanding"]:
            if needed not in cols:
                raise RuntimeError("bondret column missing: " + needed)
        sql = (
            "with b as (select date, cusip, ret_eom, rating_num, "
            " lag(amount_outstanding) over (partition by cusip order by date) as w "
            " from " + library + "." + table + " where date between %(s)s and %(e)s) "
            "select date, "
            " sum(case when rating_num between 1 and 10 then ret_eom * w end) / "
            "   nullif(sum(case when rating_num between 1 and 10 then w end), 0) as ig, "
            " sum(case when rating_num between 11 and 21 then ret_eom * w end) / "
            "   nullif(sum(case when rating_num between 11 and 21 then w end), 0) as hy, "
            " count(*) as n "
            "from b where ret_eom is not null and w is not null and w > 0 "
            "group by date order by date")
        raw = db.raw_sql(sql, params={"s": start_date, "e": end_date}, date_cols=["date"])
    finally:
        wrds_client.release(db)
    rows = []
    src = "wrds:" + library + "." + table
    for i in range(len(raw)):
        month_end = raw["date"].iloc[i] + pd.offsets.MonthEnd(0)
        for col, sid in [("ig", "ig_credit"), ("hy", "hy_credit")]:
            v = raw[col].iloc[i]
            if pd.isna(v):
                continue
            rows.append({"month_end": month_end, "series_id": sid, "value": float(v),
                         "quantity": "total_return", "provenance": "index_derived",
                         "source": src + ".ret_eom:vw_" + col})
    return finalize_rows(rows)
