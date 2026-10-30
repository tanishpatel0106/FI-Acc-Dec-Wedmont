"""Modern multi-asset ETF proxies from the CRSP monthly stock file.

PERMNOs are resolved by ticker AND date range through the CRSP names table, never by
ticker alone, because tickers are recycled.
"""
import pandas as pd

from lifecycle.data import wrds_client
from lifecycle.data.schema import finalize_rows

# ticker -> (canonical series id, earliest plausible listing date of the intended fund)
ETFS = {
    "EFA": ("intl_eq", "2001-08-01"),
    "EEM": ("em_eq", "2003-04-01"),
    "LQD": ("ig_credit_etf", "2002-07-01"),
    "TIP": ("tips", "2003-12-01"),
    "VNQ": ("reit", "2004-09-01"),
    "IEF": ("ust_7_10_etf", "2002-07-01"),
    "TLT": ("ust_20p_etf", "2002-07-01"),
    "GLD": ("gold", "2004-11-01"),
}


def _resolve_permnos(db) -> dict[str, list[tuple[int, pd.Timestamp, pd.Timestamp]]]:
    out: dict[str, list[tuple[int, pd.Timestamp, pd.Timestamp]]] = {}
    tickers = "', '".join(ETFS.keys())
    if wrds_client.table_exists(db, "crsp", "stksecurityinfohist"):
        sql = ("select permno, ticker, secinfostartdt as d0, secinfoenddt as d1 from crsp.stksecurityinfohist "
               "where ticker in ('" + tickers + "')")
    else:
        sql = ("select permno, ticker, namedt as d0, nameendt as d1 from crsp.msenames "
               "where ticker in ('" + tickers + "')")
    names = db.raw_sql(sql, date_cols=["d0", "d1"])
    for i in range(len(names)):
        ticker = str(names["ticker"].iloc[i])
        sid, listed = ETFS[ticker]
        d0 = names["d0"].iloc[i]
        d1 = names["d1"].iloc[i]
        if pd.isna(d1):
            d1 = pd.Timestamp("2100-01-01")
        # keep only name spells that overlap the intended fund's life
        if d1 < pd.Timestamp(listed):
            continue
        out.setdefault(ticker, []).append((int(names["permno"].iloc[i]), max(d0, pd.Timestamp(listed)), d1))
    return out


def pull_etfs(end_date: str = "2100-01-01") -> pd.DataFrame:
    db = wrds_client.connect()
    rows = []
    try:
        spells = _resolve_permnos(db)
        use_ciz = wrds_client.table_exists(db, "crsp", "msf_v2")
        for ticker in ETFS:
            if ticker not in spells:
                print("warning: no CRSP name spell for", ticker)
                continue
            sid = ETFS[ticker][0]
            seen = set()
            for permno, d0, d1 in spells[ticker]:
                if use_ciz:
                    sql = ("select mthcaldt as date, mthret as ret from crsp.msf_v2 where permno = %(p)s "
                           "and mthcaldt between %(s)s and %(e)s order by mthcaldt")
                else:
                    sql = ("select date, ret from crsp.msf where permno = %(p)s "
                           "and date between %(s)s and %(e)s order by date")
                raw = db.raw_sql(sql, params={"p": permno, "s": d0.date().isoformat(),
                                              "e": min(d1, pd.Timestamp(end_date)).date().isoformat()},
                                 date_cols=["date"])
                for i in range(len(raw)):
                    month_end = raw["date"].iloc[i] + pd.offsets.MonthEnd(0)
                    v = raw["ret"].iloc[i]
                    if pd.isna(v) or month_end in seen:
                        continue
                    seen.add(month_end)
                    rows.append({"month_end": month_end, "series_id": sid, "value": float(v),
                                 "quantity": "total_return", "provenance": "observed",
                                 "source": "wrds:crsp.msf." + ticker + "." + str(permno)})
    finally:
        wrds_client.release(db)
    return finalize_rows(rows)
