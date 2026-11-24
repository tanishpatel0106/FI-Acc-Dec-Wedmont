"""Reproduce and extend the November 10 employer demonstration.

Run with backend/.venv/Scripts/python.exe research/validate_followup.py --stage all.
Use --dataset observed for the separate public-ETF validation panel.
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "followup_2026_11_19"


def save(name, value):
    from lifecycle.runs.jsonsafe import clean

    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(clean(value), indent=2, default=str), encoding="utf-8")


def execute(kind, spec, label):
    from lifecycle.runs import executor, registry

    rid = executor.run_sync(kind, spec, label)
    row = registry.get(rid)
    print(label, rid, row["status"], flush=True)
    if row["status"] != "done":
        raise RuntimeError(row.get("error"))
    result = registry.load_results(rid)
    save(rid + ".json", result)
    return {"run_id": rid, "kind": kind, "label": label, "spec": row["spec"],
            "catalog_hash": row["catalog_hash"], "engine_version": row["engine_version"]}


def baseline():
    from lifecycle.runs import registry

    ids = json.loads((OUT / "baseline_run_ids.json").read_text())
    for kind in ("frontier", "signed_flow"):
        rid = ids[kind]["run_id"]
        save("baseline_" + kind + ".json", registry.load_results(rid))


def studies():
    from lifecycle.runs import registry
    from lifecycle.studies import registry as studies_registry
    from lifecycle.studies.historical_replay import HistoricalReplaySpec, ReplayInvestor
    from lifecycle.studies.lifecycle_sim import LifecycleSimSpec

    results = {}
    for kind in ("frontier", "signed_flow", "rebalance", "scenario_lab", "optimize", "compare_v2", "asof"):
        results[kind] = execute(kind, studies_registry.spec_model(kind)(), "corrected default " + kind)
    evidence = studies_registry.spec_model("evidence")(
        study_ids={k: v["run_id"] for k, v in results.items()})
    results["evidence"] = execute("evidence", evidence, "corrected baseline evidence")
    investor = ReplayInvestor(start_age=30)
    results["historical_replay"] = execute("historical_replay", HistoricalReplaySpec(
        start="2006-01", investor=investor, experiments=True,
        policies=("sixty_forty", "target_date", "lifecycle_adaptive")), "employer demo: age 30 in January 2006")
    results["lifecycle_sim"] = execute("lifecycle_sim", LifecycleSimSpec(
        start="2006-01", investor=investor), "dated lifecycle simulation: January 2006 information")
    results["multi_asset"] = execute("multi_asset", studies_registry.spec_model("multi_asset")(),
                                      "default public multi-asset study")
    save("main_runs.json", results)
    registry_report = {k: registry.get(v["run_id"])["status"] for k, v in results.items()}
    save("main_status.json", registry_report)


def frontiers(dataset):
    from lifecycle.studies.common import (
        StudyCosts,
        StudyData,
        StudyInvestor,
        StudyScenario,
    )
    from lifecycle.studies.frontier import FrontierSpec
    from lifecycle.studies.permanent import PermanentSpec

    configs = [("1953_full", "core_long_history", "ust_10y", "1953-01-01", "2026-09-30"),
               ("1990_onward", "core_long_history", "ust_10y", "1990-01-01", "2026-09-30"),
               ("matched_model", "core_long_history", "ust_10y", "2002-09-01", "2026-09-30"),
               ("matched_model_2002_2013", "core_long_history", "ust_10y", "2002-09-01", "2013-12-31"),
               ("matched_model_2014_onward", "core_long_history", "ust_10y", "2014-01-01", "2026-09-30")]
    if dataset == "observed":
        configs = [("matched_ief", "observed_treasury_etf", "ust_7_10_etf", "2002-09-01", "2026-09-30"),
                   ("ief_2002_2013", "observed_treasury_etf", "ust_7_10_etf", "2002-09-01", "2013-12-31"),
                   ("ief_2014_onward", "observed_treasury_etf", "ust_7_10_etf", "2014-01-01", "2026-09-30")]
    results = {}
    for label, universe, bond, start, end in configs:
        spec = FrontierSpec(data=StudyData(universe=universe, calibration_start=start, calibration_end=end),
                            scenario=StudyScenario(n_paths=5000, n_train_paths=2000, seed=20261119, k_regimes=1),
                            investor=StudyInvestor(horizon_years=40), bond=bond, r_start=0.03, r_stop=0.06,
                            r_step=0.0025, n_boot=300, alt_generators=("student_t",), alt_windows=(),
                            gammas=(2, 4, 6, 8), bond_assets=("tbill", bond))
        results[label] = execute("frontier", spec, label)
        if label in ("1990_onward", "matched_ief"):
            cost_spec = spec.model_copy(update={"costs": StudyCosts(half_spread_bps=5)})
            results[label + "_cost5bps"] = execute("frontier", cost_spec, label + " with 5bp trading costs")
    if dataset == "observed":
        results["permanent_with_observed_gold"] = execute("permanent", PermanentSpec(),
                                                           "classic Permanent Portfolio with observed GLD")
    save(dataset + "_frontier_runs.json", results)


def holdout(dataset, end_date="2026-09-30", start_date=None, respect_publication_lags=False):
    """Freeze allocations on pre-split bootstrap paths, score completed post-split historical cohorts."""
    from lifecycle.data import panel
    from lifecycle.runs import context as C
    from lifecycle.studies import common as S

    universe = "observed_treasury_etf" if dataset == "observed" else "core_long_history"
    bond = "ust_7_10_etf" if dataset == "observed" else "ust_10y"
    ages = (35, 55, 65, 85)
    qs = (-0.05, -0.02, 0, 0.02, 0.04, 0.06)
    bs = np.round(np.arange(0, 1.001, 0.1), 2)
    data_start = start_date or ("2002-09-01" if dataset == "observed" else "1953-01-01")
    splits = (2008, 2012, 2015) if dataset == "observed" else (1990, 2000, 2005, 2010, 2015)
    rows, fitted = [], []
    for horizon in (10, 20):
        for split in splits:
            train_end = f"{split - 1}-12-31"
            latest_publication = None
            if respect_publication_lags:
                from calibration_cutoff import known_history_end
                train_end, latest_publication = known_history_end(universe, train_end, f"{split}-01-01")
            train_data = S.StudyData(universe=universe, calibration_start=data_start,
                                     calibration_end=train_end)
            test_data = S.StudyData(universe=universe, calibration_start=f"{split}-01-01",
                                    calibration_end=end_date)
            available = len(panel.universe_data(universe, test_data.calibration_start, test_data.calibration_end).real)
            if available < horizon * 12:
                continue
            train_ce = np.zeros((len(ages), len(qs), len(bs)))
            outcomes = {}
            for ai, age in enumerate(ages):
                h = min(horizon, 95 - age)
                inv = S.StudyInvestor(age=age, retirement_age=65, horizon_years=h)
                scen = S.StudyScenario(n_paths=4000, n_train_paths=4000, seed=20261119, k_regimes=1)
                es = S.experiment_spec(train_data, scen, inv)
                train = S.get_context(es, S.get_tensor(es), es.scenario.seed)
                hist_es = S.experiment_spec(test_data, scen.model_copy(update={"generator": "historical"}), inv)
                historical_tensor = S.get_tensor(hist_es)
                history = S.get_context(hist_es, historical_tensor, hist_es.scenario.seed)
                for qi, q in enumerate(qs):
                    for bi, b in enumerate(bs):
                        weights = S.weights_vector({"us_eq": 1 - b, bond: b}, train.tensor.assets)
                        a = S.run(train, weights, S.strategy("calendar_12m"), spend="signed", q=q, zero_income=True)
                        z = S.run(history, weights, S.strategy("calendar_12m"), spend="signed", q=q, zero_income=True)
                        train_ce[ai, qi, bi] = S.resources_ce(a.terminal, a.funded, 4)
                        outcomes[ai, qi, bi] = z
                C._TENSORS.clear()
            best = train_ce.argmax(axis=2)
            age_only = (train_ce / train_ce.max(axis=2, keepdims=True)).sum(axis=1).argmax(axis=1)
            for ai, age in enumerate(ages):
                for qi, q in enumerate(qs):
                    full = outcomes[ai, qi, best[ai, qi]]
                    restricted = outcomes[ai, qi, age_only[ai]]
                    ce_full = S.resources_ce(full.terminal, full.funded, 4)
                    ce_age = S.resources_ce(restricted.terminal, restricted.funded, 4)
                    rows.append({"dataset": dataset, "split_year": split, "max_horizon": horizon,
                                 "age": age, "actual_horizon": min(horizon, 95 - age), "q": q,
                                 "full_bond_share": bs[best[ai, qi]], "age_only_bond_share": bs[age_only[ai]],
                                 "full_ce_resources": ce_full, "age_only_ce_resources": ce_age,
                                 "full_vs_age_delta": ce_full / ce_age - 1,
                                 "full_success": float((full.first_shortfall < 0).mean()),
                                 "age_only_success": float((restricted.first_shortfall < 0).mean()),
                                 "n_overlapping_cohorts": len(full.terminal),
                                 "train_end": train_data.calibration_end, "test_start": test_data.calibration_start,
                                 "latest_training_publication": latest_publication,
                                 "catalog_hash": panel.catalog_hash()})
            fitted.append({"split_year": split, "horizon": horizon, "best_b": bs[best].tolist(),
                           "age_only_b": bs[age_only].tolist(), "train_ce": train_ce.tolist()})
            print("chronological holdout", dataset, split, horizon, flush=True)
    pd.DataFrame(rows).to_csv(OUT / f"{dataset}_chronological_holdout.csv", index=False)
    save(f"{dataset}_holdout_specs.json", {"ages": ages, "q": qs, "bond_grid": bs.tolist(),
          "gamma": 4, "train_paths": 4000, "seed": 20261119, "catalog_hash": panel.catalog_hash(),
          "respect_recorded_publication_lags": respect_publication_lags,
          "cell_weighting": "equal weights over the declared age and signed-flow grid",
          "objective": "CRRA certainty equivalent of terminal real wealth plus funded draws, USD 1000 floor",
          "inference": "descriptive completed overlapping cohorts, without iid confidence intervals", "fitted": fitted})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("baseline", "studies", "frontiers", "holdout", "all"), default="all")
    parser.add_argument("--dataset", choices=("main", "observed"), default="main")
    args = parser.parse_args()
    if args.dataset == "observed":
        os.environ["LIFECYCLE_DATA_DIR"] = "data/validation_etfs"
    os.environ.setdefault("NUMBA_NUM_THREADS", "4")
    if args.stage == "baseline":
        baseline()
    if args.stage in ("studies", "all") and args.dataset == "main":
        studies()
    if args.stage in ("frontiers", "all"):
        frontiers(args.dataset)
    if args.stage in ("holdout", "all"):
        holdout(args.dataset)


if __name__ == "__main__":
    main()
