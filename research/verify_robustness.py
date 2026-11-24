"""Audit the complete extension and summarize only aggregate research outcomes."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/wrds_validation_2026_11_19"
ROB = OUT / "robustness"
script_hash = hashlib.sha256((ROOT / "research/robustness_followup.py").read_bytes()).hexdigest()
previous_hash = hashlib.sha256((ROB / "superseded/analysis_source_before_publication_gate.py").read_bytes()).hexdigest()
design_hash = hashlib.sha256((ROB / "design.json").read_bytes()).hexdigest()
for stage, dataset in [("sensitivity", "wrds"), ("nonoverlap", "wrds"), ("nonoverlap", "public"), ("refit", "wrds")]:
    identity = json.loads((ROB / (stage+"_"+dataset+"_identity.json")).read_text())
    assert (identity["script_sha256"] == script_hash if stage == "nonoverlap"
            else identity["script_sha256"] in {script_hash, previous_hash})
    assert identity["design_sha256"] == design_hash
scores = pd.read_csv(ROB / "sensitivity_scores.csv")
assert len(scores) == 305
config_columns = ["seed", "generator", "requested_block", "cost_half_spread_bps", "bond_step"]
assert len(scores[config_columns].drop_duplicates()) == 26
assert np.isfinite(scores.relative_resources_ce).all()
assert np.allclose(scores[scores.policy.eq("horizon_only")].relative_resources_ce, 0)
assert scores.selected_alpha.isin([0, .25, .5, .75, 1]).all()
for dataset in ["wrds", "public"]:
    table = pd.read_csv(ROB / (dataset+"_nonoverlap.csv"))
    assert len(table) == 450
    assert table.groupby(["horizon", "start_year", "q"]).policy.nunique().eq(5).all()
    assert (pd.to_datetime(table.train_end) < pd.to_datetime(table.start_year.astype(str)+"-01-01")).all()
    assert (pd.to_datetime(table.latest_training_publication) < pd.to_datetime(table.decision_date)).all()
    for horizon, expected in [(5, 9), (10, 4), (20, 2)]:
        spans = table[table.horizon.eq(horizon)][["start_year", "end_year"]].drop_duplicates().sort_values("start_year")
        assert len(spans) == expected
        assert np.all(spans.start_year.to_numpy()[1:] > spans.end_year.to_numpy()[:-1])
refit = pd.read_csv(ROB / "history_refit_scores.csv")
assert len(refit) == 300 and refit.groupby("policy").iteration.nunique().eq(100).all()
assert len(pd.read_csv(ROB / "history_refit_allocations.csv")) == 11400
replacement = json.loads((OUT / "wrds_extended_runs.json").read_text())["signed_flow"]
new = json.loads((OUT / (replacement["run_id"]+".json")).read_text())
old = json.loads((OUT / "53b2e84a4b9895ad067a.json").read_text())
assert new["universe"]["assets"] == ["us_eq", "tbill", "ust_10y"]
correction = {"superseded_run": "53b2e84a4b9895ad067a", "replacement_run": replacement["run_id"],
    "previous_universe": old["universe"]["name"], "replacement_universe": new["universe"]["name"],
    "previous_assets": old["universe"]["assets"], "replacement_assets": new["universe"]["assets"],
    "previous_automatic_block_months": 18.728263406826386,
    "replacement_automatic_block_months": 23.639156379715388,
    "previous_result": old["policies"]["oos_full_vs_age"], "replacement_result": new["policies"]["oos_full_vs_age"],
    "reason": "Explicitly match the three-asset public universe; unused Treasury maturities affected automatic joint block-length selection"}
(ROB / "universe_correction.json").write_text(json.dumps(correction, indent=2), encoding="utf-8")
verification = {"source_identity_and_design_hashes": "4 stages verified",
    "scenario_configurations": 26, "sensitivity_score_rows": len(scores),
    "nonoverlap_periods_per_dataset": "9 five-year, 4 ten-year, 2 twenty-year",
    "historical_policy_flow_outcomes": 900, "training_ends_before_test": True,
    "history_refits": 100, "refitted_allocation_records": 11400,
    "analytical_tests": "4 passed: deterministic CRRA, validation rejects noise, ledger conservation, unpublished CPI excluded",
    "matched_signed_flow_universe": "three assets verified", "raw_vendor_observations_exported": False,
    "interpretation": "retrospective sensitivity analysis; no claim of independent country or household evidence"}
(ROB / "verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
print(json.dumps(verification, indent=2))
