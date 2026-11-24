"""Run inside authenticated WRDS Cloud. Never print restricted observations."""
import base64
import hashlib
import json
import os
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2

OUT = Path.home() / "fixed_income_validation_20261119"
OUT.mkdir(exist_ok=True)
connection = psycopg2.connect(host=os.getenv("PGHOST", "wrds-pgdata.wharton.upenn.edu"), port=9737,
                             dbname="wrds", user=os.environ["USER"], sslmode="require")
connection.autocommit = True
summary = {"extracted_at": pd.Timestamp.now(tz="UTC").isoformat(), "sources": {}}


def query(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return pd.DataFrame(cursor.fetchall(), columns=[c.name for c in cursor.description])


jobs = {
    "mcti": "select * from crsp.mcti where caldt >= '1925-12-01' order by caldt",
    "msix": "select caldt,vwretd,vwindd from crsp.msix where caldt >= '1925-12-01' order by caldt",
    "etfs": """select mthcaldt,permno,ticker,mthret,mthretx from crsp.msf_v2
        where ticker in ('IEF','TLT','GLD','EFA','EEM','LQD','TIP','VNQ','DBC','HYG')
        and mthcaldt >= '2000-01-01' order by ticker,mthcaldt,permno""",
    "credit": """with b as (
        select date, cusip, ret_eom,
          lag(date) over w as prior_date,
          lag(rating_num) over w as prior_rating,
          lag(amount_outstanding) over w as prior_amount
        from wrdsapps_bondret.bondret where date >= '2002-07-01'
        window w as (partition by cusip order by date)
      ) select date,
        sum(ret_eom*prior_amount) filter (where prior_rating between 1 and 10)
          /nullif(sum(prior_amount) filter (where prior_rating between 1 and 10),0) as ig,
        sum(ret_eom*prior_amount) filter (where prior_rating between 11 and 21)
          /nullif(sum(prior_amount) filter (where prior_rating between 11 and 21),0) as hy,
        count(*) filter (where prior_rating between 1 and 10) as n_ig,
        count(*) filter (where prior_rating between 11 and 21) as n_hy
      from b where ret_eom is not null and prior_amount>0
        and date_trunc('month',date)=date_trunc('month',prior_date)+interval '1 month'
      group by date order by date""",
}
files = []
for name, sql in jobs.items():
    try:
        frame = query(sql)
        path = OUT / (name + ".csv")
        frame.to_csv(path, index=False)
        files.append(path)
        datecol = "mthcaldt" if name == "etfs" else "date" if name == "credit" else "caldt"
        record = {"rows": len(frame), "start": str(frame[datecol].min()),
                  "end": str(frame[datecol].max()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if name == "etfs":
            record["ticker_counts"] = frame.groupby("ticker").size().to_dict()
            record["permnos_per_ticker"] = frame.groupby("ticker").permno.nunique().to_dict()
        elif name != "credit":
            checks = {}
            prefixes = ["b2", "b5", "b10", "b20", "b30", "t30", "cpi"] if name == "mcti" else ["vw"]
            for prefix in prefixes:
                ret = prefix + "ret" if prefix != "vw" else "vwretd"
                ind = prefix + "ind" if prefix != "vw" else "vwindd"
                r = pd.to_numeric(frame[ret], errors="coerce").astype(float)
                implied = pd.to_numeric(frame[ind], errors="coerce").astype(float).pct_change(fill_method=None)
                checks[ret] = {"decimal_rmse": float(np.sqrt(((r-implied)**2).mean())),
                               "percent_rmse": float(np.sqrt(((r/100-implied)**2).mean())),
                               "n": int((r.notna() & implied.notna()).sum())}
            record["unit_checks_against_index_growth"] = checks
        summary["sources"][name] = record
        print(name, "extracted", len(frame), "observations; raw values suppressed", flush=True)
    except Exception as exc:
        summary["sources"][name] = {"error_type": type(exc).__name__, "error": str(exc)[:180]}
        print(name, type(exc).__name__, flush=True)
connection.close()
metadata = OUT / "extraction_summary.json"
metadata.write_text(json.dumps(summary, indent=2), encoding="utf-8")
files.append(metadata)
archive = OUT / "wrds_inputs.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as target:
    for path in files:
        target.write(path, path.name)
(OUT / "transfer.txt").write_text(base64.b64encode(archive.read_bytes()).decode("ascii"), encoding="ascii")
print(json.dumps(summary, indent=2))
print("Archive ready; bytes:", archive.stat().st_size)
