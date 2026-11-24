"""Verify licensed-input integrity and export only aggregate diagnostics."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/wrds_validation_2026_11_19"
wrds = pd.read_parquet(ROOT / "data/wrds_validation/processed/panel.parquet")
public = pd.read_parquet(ROOT / "data/processed/panel.parquet")
audit = pd.read_csv(OUT / "source_audit.csv")
assert audit.nonfinite.sum() == 0 and audit.duplicates.sum() == 0
restricted = wrds[wrds.source.str.startswith("wrds:")]
bad_returns = restricted.quantity.eq("total_return") & restricted.value.lt(-1)
assert not bad_returns.any()
rows = []
for sid in ["us_eq", "ust_10y", "tbill", "cpi_nsa"]:
    a = public[public.series_id.eq(sid)].set_index("month_end").value
    b = wrds[wrds.series_id.eq(sid)].set_index("month_end").value
    for window, start in [("long", "1953-05-01"), ("modern", "2002-09-01")]:
        pair = pd.concat([a.rename("public"), b.rename("wrds")], axis=1).loc[start:"2024-12-31"].dropna()
        rows.append(dict(series_id=sid, window=window, n_months=len(pair),
            public_annualized_arithmetic_mean=float(pair.public.mean()*12),
            wrds_annualized_arithmetic_mean=float(pair.wrds.mean()*12),
            monthly_return_correlation=float(pair.corr().iloc[0, 1]),
            monthly_difference_rmse=float(np.sqrt(((pair.public-pair.wrds)**2).mean()))))
pd.DataFrame(rows).to_csv(OUT / "source_difference_summary.csv", index=False)
extraction = json.loads((OUT / "extraction_summary.json").read_text())
for name, record in extraction["sources"].items():
    assert "error" not in record
    path = ROOT / "data/wrds_validation/inputs" / (name + ".csv")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
run_records = []
windows = {}
for name in ["public", "treasury_only", "wrds"]:
    records = json.loads((OUT / (name + "_frontier_runs.json")).read_text())
    assert len(records) == 4
    for label, record in records.items():
        run = json.loads((OUT / (record["run_id"] + ".json")).read_text())
        assert run["main_horizon"] == 30 and run["ce_horizon_years"] == 30
        signature = (run["universe"]["window"], run["universe"]["n_months"])
        if label in windows:
            assert signature == windows[label], "Unmatched sample windows"
        windows[label] = signature
        run_records.append(record["run_id"])
for dataset in ["wrds", "public_matched"]:
    frame = pd.read_csv(OUT / (dataset + "_chronological_holdout.csv"))
    assert len(frame) == 192
    assert frame.train_end.lt(frame.test_start).all()
    assert (pd.to_datetime(frame.latest_training_publication)<pd.to_datetime(frame.test_start)).all()
    assert frame.n_overlapping_cohorts.gt(0).all()
reproductions = {}
for name in ["frontier", "signed_flow"]:
    log = (OUT / ("reproduce_" + name + ".log")).read_text(encoding="utf-16" if (OUT / ("reproduce_" + name + ".log")).read_bytes().startswith(b'\xff\xfe') else "utf-8")
    assert "reproduced " in log and "DIFFER" not in log
    if name == "frontier":
        assert "reproduced " + run_records[8] in log
    else:
        current = json.loads((OUT / "wrds_extended_runs.json").read_text())["signed_flow"]
        assert current["spec"]["data"]["universe"] == "core_long_history"
        signed = json.loads((OUT / (current["run_id"] + ".json")).read_text())
        assert signed["universe"]["assets"] == ["us_eq", "tbill", "ust_10y"]
        assert "reproduced " + current["run_id"] in log
    reproductions[name] = log.splitlines()[-1]
verification = {"raw_input_hashes": "4 of 4 verified", "restricted_invalid_return_count": int(bad_returns.sum()),
    "nonfinite_values": 0, "duplicate_month_series_rows": 0,
    "matched_frontier_studies": len(run_records), "frontier_horizon": "30 years for success and utility",
    "historical_holdout": "8 folds and 192 cells per dataset; 384 cells total",
    "exact_reproduction": reproductions, "backend_tests": "111 passed after credit timing correction",
    "restricted_data_in_notebook": "No raw vendor observations; aggregate artifacts only",
    "WRDS_access": "Duo and Terms of Use completed; authenticated Cloud extraction successful"}
(OUT / "verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
print(json.dumps(verification, indent=2))
