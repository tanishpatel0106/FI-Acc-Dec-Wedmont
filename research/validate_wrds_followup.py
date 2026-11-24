"""Matched-window WRDS source sensitivity and independent allocation validation."""
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/wrds_validation_2026_11_19"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["public", "treasury_only", "wrds"], required=True)
    parser.add_argument("--stage", choices=["long", "frontiers", "extended", "all"], default="all")
    args = parser.parse_args()
    name = args.dataset
    os.environ["LIFECYCLE_DATA_DIR"] = str(ROOT / "data" / (
        "wrds_validation" if name == "wrds" else "wrds_treasury_bridge" if name == "treasury_only" else ""))
    os.environ.setdefault("NUMBA_NUM_THREADS", "4")
    from numba import set_num_threads
    set_num_threads(4)
    import validate_followup as F
    F.OUT = OUT
    from lifecycle.studies import common as S
    from lifecycle.studies.frontier import FrontierSpec
    from lifecycle.data import panel
    records = json.loads((OUT / (name + "_frontier_runs.json")).read_text()) if args.stage == "long" else {}
    if args.stage in ("long", "frontiers", "all"):
        for window, start, end in [
            ("long", "1953-05-01", "2024-12-31"),
            ("modern", "2002-09-01", "2024-12-31"),
            ("early", "2002-09-01", "2013-12-31"),
            ("recent", "2014-01-01", "2024-12-31"),
        ]:
            if args.stage == "long" and window != "long":
                continue
            spec = FrontierSpec(data=S.StudyData(universe="core_long_history", calibration_start=start,
                calibration_end=end), scenario=S.StudyScenario(n_paths=10000, n_train_paths=5000,
                seed=20261119, k_regimes=1), investor=S.StudyInvestor(horizon_years=30),
                bond="ust_10y", r_start=0.03, r_stop=0.06, r_step=0.0025,
                n_boot=300, alt_generators=("student_t",), alt_windows=(), gammas=(4,),
                bond_assets=("tbill", "ust_10y"))
            records[window] = F.execute("frontier", spec, name + " matched " + window)
        F.save(name + "_frontier_runs.json", records)
    if args.stage in ("extended", "all") and name == "wrds":
        records = {}
        from lifecycle.studies.signed_flow import SignedFlowSpec
        from lifecycle.studies.permanent import PermanentSpec
        from lifecycle.studies.registry import spec_model
        signed = SignedFlowSpec(data=S.StudyData(universe="core_long_history",
            calibration_start="1953-01-01", calibration_end="2024-12-31"),
            scenario=S.StudyScenario(n_paths=5000, n_train_paths=4000, seed=20261119, k_regimes=1), n_boot=300)
        records["signed_flow"] = F.execute("signed_flow", signed, "WRDS age and signed cash flow")
        records["permanent"] = F.execute("permanent", PermanentSpec(data=S.StudyData(
            universe="pp_modern_etf", calibration_start="2004-12-01", calibration_end="2024-12-31")),
            "WRDS Permanent Portfolio, complete fund months")
        multi = spec_model("multi_asset")()
        multi = multi.model_copy(update={"data": multi.data.model_copy(update={"universe": "multi_asset_full",
            "calibration_start": "2007-05-01", "calibration_end": "2024-12-31"})})
        records["multi_asset"] = F.execute("multi_asset", multi, "WRDS full multi-asset baseline")
        F.save("wrds_extended_runs.json", records)
        F.holdout("wrds", end_date="2024-12-31", start_date="1953-05-01", respect_publication_lags=True)
        import validate_allocation_holdout as A
        A.OUT = OUT
        A.run(end_date="2024-12-31", dataset_name="wrds")
    F.save(name + "_validation_metadata.json", {"dataset": name, "catalog_hash": panel.catalog_hash(),
        "engine_version": __import__("lifecycle.config", fromlist=["engine_version"]).engine_version(),
        "matched_end": "2024-12-31", "hypotheses": "Source sensitivity, not empirical household risk tolerance",
        "selection": "Retrospective extension after the public-data analysis; not preregistered"})


if __name__ == "__main__":
    main()
