"""Import local licensed CRSP extracts without displaying any observations."""
import hashlib
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
os.environ["LIFECYCLE_DATA_DIR"] = str(ROOT / "data/wrds_validation")
from lifecycle.data.ingest_etfs import ETFS
from lifecycle.data.ingest_crsp_mcti import CANONICAL
from lifecycle.data.normalize import write_raw, build_panel
from lifecycle.data.schema import finalize_rows

INPUT = ROOT / "data/wrds_validation/inputs"
OUT = ROOT / "research/wrds_validation_2026_11_19"
OUT.mkdir(exist_ok=True)
metadata = json.loads((INPUT / "extraction_summary.json").read_text())
for name, record in metadata["sources"].items():
    if "error" in record:
        continue
    assert hashlib.sha256((INPUT / (name + ".csv")).read_bytes()).hexdigest() == record["sha256"]
for group in (ROOT / "data/raw").iterdir():
    if group.is_dir():
        shutil.copytree(group, ROOT / "data/wrds_validation/raw" / group.name, dirs_exist_ok=True)
rows = []
for filename, datecol, mapping in [
    ("mcti", "caldt", CANONICAL), ("msix", "caldt", {"vwretd": "us_eq"}),
]:
    frame = pd.read_csv(INPUT / (filename + ".csv"), parse_dates=[datecol])
    for col, sid in mapping.items():
        check = metadata["sources"][filename]["unit_checks_against_index_growth"][col]
        assert check["decimal_rmse"] < check["percent_rmse"], "Unresolved return units"
        for day, value in zip(frame[datecol], pd.to_numeric(frame[col], errors="coerce")):
            if np.isfinite(value):
                rows.append(dict(month_end=day, series_id=sid, value=value,
                    quantity="rate" if col == "cpiret" else "total_return", provenance="observed",
                    source=f"wrds:crsp.{filename}.{col}"))
write_raw(finalize_rows([r for r in rows if r["series_id"] != "cpi_nsa"]), "wrds_cloud", "core")
write_raw(finalize_rows([r for r in rows if r["series_id"] == "cpi_nsa"], publication_lag_days=15), "wrds_cloud", "inflation")
etfs = pd.read_csv(INPUT / "etfs.csv", parse_dates=["mthcaldt"])
etf_rows = []
for ticker, (sid, inception) in ETFS.items():
    part = etfs[(etfs.ticker == ticker) & (etfs.mthcaldt >= inception)]
    assert part.permno.nunique() == 1
    assert not part.mthcaldt.duplicated().any()
    for day, value in zip(part.mthcaldt, pd.to_numeric(part.mthret, errors="coerce")):
        if np.isfinite(value) and value >= -1:
            etf_rows.append(dict(month_end=day, series_id=sid, value=value, quantity="total_return",
                provenance="observed", source=f"wrds:crsp.msf_v2.mthret.{ticker}"))
write_raw(finalize_rows(etf_rows), "wrds_cloud", "etfs")
if (INPUT / "credit.csv").exists():
    credit = pd.read_csv(INPUT / "credit.csv", parse_dates=["date"])
    credit_rows = []
    for col, sid in [("ig", "ig_credit"), ("hy", "hy_credit")]:
        for day, value in zip(credit.date, pd.to_numeric(credit[col], errors="coerce")):
            if np.isfinite(value):
                credit_rows.append(dict(month_end=day, series_id=sid, value=value, quantity="total_return",
                    provenance="index_derived", source=f"wrds:wrdsapps_bondret.lagged_rating_amount.{col}"))
    write_raw(finalize_rows(credit_rows), "wrds_cloud", "credit")
result = build_panel()
from lifecycle.data import panel
panel.reload()
audit = []
for sid, group in panel.panel().groupby("series_id"):
    dates = group.month_end.dt.to_period("M")
    audit.append(dict(series_id=sid, source=group.source.iloc[0], months=len(group),
        start=str(group.month_end.min().date()), end=str(group.month_end.max().date()),
        internal_missing_months=int(dates.max().ordinal-dates.min().ordinal+1-len(group)),
        nonfinite=int((~np.isfinite(group.value)).sum()), duplicates=int(dates.duplicated().sum())))
pd.DataFrame(audit).to_csv(OUT / "source_audit.csv", index=False)
(OUT / "extraction_summary.json").write_text(json.dumps(metadata, indent=2))
(OUT / "panel_build.json").write_text(json.dumps(result, indent=2))
print(json.dumps({"catalog_hash": result["catalog_hash"], "series": result["n_series"],
    "raw_observations_suppressed": True, "audit": str(OUT / "source_audit.csv")}, indent=2))
os.environ["LIFECYCLE_DATA_DIR"] = str(ROOT / "data/wrds_treasury_bridge")
for group in (ROOT / "data/raw").iterdir():
    if group.is_dir():
        shutil.copytree(group, ROOT / "data/wrds_treasury_bridge/raw" / group.name, dirs_exist_ok=True)
write_raw(finalize_rows([r for r in rows if r["series_id"].startswith("ust_")]), "wrds_cloud", "treasuries")
bridge = build_panel()
(OUT / "treasury_bridge_build.json").write_text(json.dumps(bridge, indent=2))
print("Treasury-only bridge catalog:", bridge["catalog_hash"])
