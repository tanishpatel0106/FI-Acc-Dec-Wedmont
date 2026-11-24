"""Fit CE/success-optimal bond shares on training paths and score on separate test paths."""
import json
import os
from pathlib import Path

import numpy as np
from lifecycle.data import panel
from lifecycle.runs.jsonsafe import clean
from lifecycle.studies import common as S
from numba import set_num_threads

OUT = Path(__file__).resolve().parent / "followup_2026_11_19"


def run(observed=False, end_date="2026-09-30", dataset_name=None):
    set_num_threads(4)
    if observed:
        os.environ["LIFECYCLE_DATA_DIR"] = "data/validation_etfs"
        panel.reload()
    name = dataset_name or ("observed" if observed else "main")
    data = S.StudyData(universe="observed_treasury_etf" if observed else "core_long_history",
                       calibration_start="2002-09-01" if observed else "1953-01-01",
                       calibration_end=end_date)
    bond = "ust_7_10_etf" if observed else "ust_10y"
    scen = S.StudyScenario(n_paths=10000, n_train_paths=5000, seed=20261119, k_regimes=1)
    inv = S.StudyInvestor(horizon_years=30)
    _, test, train = S.train_test(data, scen, inv, S.StudyPrefs())
    bs = np.round(np.arange(0, 1.001, 0.05), 2)
    rows = []
    for rate in (0.04, 0.045, 0.05, 0.055):
        training, testing = [], []
        for b in bs:
            w = S.weights_vector({"us_eq": 1 - b, bond: b}, test.tensor.assets)
            training.append(S.run(train, w, S.strategy("calendar_12m"), rate=rate))
            testing.append(S.run(test, w, S.strategy("calendar_12m"), rate=rate))
        ce = np.array([S.ce_of(o, 4) for o in training])
        survival = np.array([(o.first_shortfall < 0).mean() for o in training])
        i_ce, i_surv = int(ce.argmax()), int(survival.argmax())
        candidate, reference = testing[i_ce], testing[i_surv]
        delta_ce = S.delta_block(candidate, reference, 4, n_boot=400)
        delta_success = S.paired_success_diff(candidate.first_shortfall < 0, reference.first_shortfall < 0)
        rows.append({"withdrawal_rate": rate, "trained_ce_bond_share": bs[i_ce],
                     "trained_survival_bond_share": bs[i_surv], "test_ce_opt_success": float((candidate.first_shortfall < 0).mean()),
                     "test_survival_opt_success": float((reference.first_shortfall < 0).mean()),
                     "test_ce_delta_ce_vs_survival": delta_ce,
                     "test_success_delta_ce_vs_survival": delta_success})
        print("allocation holdout", name, rate, bs[i_ce], bs[i_surv], flush=True)
    result = {"dataset": name, "horizon_years": 30, "gamma": 4, "train_paths": 5000, "test_paths": 10000,
              "seed": scen.seed, "data": data.model_dump(), "catalog_hash": panel.catalog_hash(),
              "bond": bond, "bond_grid": bs.tolist(), "results": rows,
              "inference": "paired simulation paths conditional on model and trained policies"}
    (OUT / f"{name}_allocation_holdout.json").write_text(json.dumps(clean(result), indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys

    run("--observed" in sys.argv)
