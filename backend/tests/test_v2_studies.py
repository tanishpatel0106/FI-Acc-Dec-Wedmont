"""Smoke tests of every v2 study and its API routes on synthetic fixtures (small path counts)."""
import time

from fastapi.testclient import TestClient

from lifecycle.api.main import app

client = TestClient(app)
SMALL = {"n_paths": 200, "n_train_paths": 150}


def _run(kind: str, spec: dict, timeout: float = 600.0) -> dict:
    r = client.post("/v1/studies/" + kind, json=spec)
    assert r.status_code == 200, r.text
    rid = r.json()["run_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get("/v1/studies/run/" + rid).json()
        if s["status"] in ("done", "failed", "cancelled"):
            return s
        time.sleep(0.3)
    raise TimeoutError(kind)


def test_lookup_does_not_launch():
    r = client.post("/v1/studies/frontier?submit=false", json={}).json()
    assert r["status"] == "none"
    assert client.get("/v1/studies/frontier/latest").json()["status"] in ("none", "done", "queued", "running")


def test_frontier_study_and_trace():
    s = _run("frontier", {"scenario": SMALL, "investor": {"horizon_years": 30}, "horizons_years": [10, 20, 30],
                          "main_horizon": 30, "r_step": 0.01, "b_step": 0.1, "n_boot": 20, "alt_n_paths": 100,
                          "alt_windows": [], "gammas": [4.0]})
    assert s["status"] == "done", s.get("error")
    res = s["results"]
    assert len(res["p_success"]["30"]) == 11 and len(res["p_success"]["30"][0]) == 11
    assert "SYNTHETIC" in " ".join(res["warnings"])
    tr = client.get("/v1/studies/run/%s/trace?r=0.04&b=0.4&path=1" % s["run_id"]).json()["trace"]
    assert len(tr["monthly"]["reason"]) == 360
    assert client.get("/v1/studies/run/%s/export?format=csv" % s["run_id"]).status_code == 200


def test_permanent_with_synthetic_gold():
    s = _run("permanent", {"scenario": SMALL, "investor": {"horizon_years": 20}, "horizons_years": [10, 20],
                           "withdrawal_grid": [0.04], "simplex_divisions": 3, "reserve_years": [0, 2], "cohort_years": 10,
                           "policies": ["sixty_forty", "pp_classic", "pp_no_gold", "pp_cash_buffer"]})
    assert s["status"] == "done", s.get("error")
    res = s["results"]
    assert {m["policy"] for m in res["scorecard"]} == {"sixty_forty", "pp_classic", "pp_no_gold", "pp_cash_buffer"}
    assert res["gold"]["available"] is True
    assert abs(sum(res["shapley"]["shapley_ce_usd"].values()) - (res["shapley"]["v_full"] - res["shapley"]["v_empty"])) < 1e-6


def test_permanent_refuses_missing_gold_universe():
    s = _run("permanent", {"data": {"universe": "pp_research_historical"}, "scenario": SMALL})
    assert s["status"] == "failed"
    assert "IncompatibleUniverse" in s["error"]


def test_rebalance_signed_flow_scenarios_asof_optimize_compare_evidence():
    inv = {"horizon_years": 20}
    for kind, spec in (
        ("rebalance", {"data": {"universe": "core"}, "scenario": SMALL, "investor": inv,
                       "allocation": {"us_eq": 0.6, "ust_10y": 0.3, "tbill": 0.1}, "cost_grid_bps": [0, 5],
                       "reserve_grid": [0, 1], "cadences": [1, 12], "bands_pp": [0.05]}),
        ("signed_flow", {"data": {"universe": "core"}, "scenario": SMALL, "ages": [45, 65], "q_grid": [-0.05, 0, 0.04],
                         "b_step": 0.25, "n_boot": 5, "horizon_years": 10, "persona_savings": [0.1],
                         "persona_start_ages": [40]}),
        ("scenario_lab", {"data": {"universe": "core"}, "scenario": SMALL, "investor": inv, "n_paths_per_generator": 150,
                          "generators": ["bootstrap", "student_t"], "cohort_years": 20,
                          "portfolios": {"60/40": {"us_eq": 0.6, "ust_10y": 0.4}, "100/0": {"us_eq": 1.0}}}),
        ("asof", {"data": {"universe": "core"}, "scenario": {**SMALL, "generator": "markov_switching"}, "investor": inv,
                  "r_grid": [0.04], "b_grid": [0.0, 0.5]}),
        ("optimize", {"data": {"universe": "core"}, "scenario": SMALL, "investor": inv, "sleeves": ["us_eq", "ust_10y", "tbill"],
                      "simplex_divisions": 4, "r_grid": [0.04], "funded_ratios": [1.0], "horizons_years": [10],
                      "generators": ["bootstrap"], "n_param_boot": 1}),
        ("compare_v2", {"data": {"universe": "core"}, "scenario": SMALL, "investor": inv, "cohort_years": 20,
                        "policies": ["sixty_forty", "all_equity", "target_date"], "generators": ["bootstrap"], "windows": []}),
        ("evidence", {"data": {"universe": "core"}, "scenario": SMALL, "walk_forward_splits": [1990],
                      "convergence_paths": [200, 400], "permutations": 20}),
    ):
        s = _run(kind, spec)
        assert s["status"] == "done", kind + ": " + str(s.get("error"))[:2000]
    ev = s["results"]
    assert len(ev["hypotheses"]) == 12
    assert all(c["status"] != "fail" for c in ev["leakage"])


def test_v2_read_routes():
    for path in ("/v1/studies", "/v1/market-state/latest", "/v1/market-state/ribbon", "/v1/fixed-income/key-rates",
                 "/v1/fixed-income/twist", "/v1/fixed-income/ladder", "/v1/data/coverage", "/v1/data/entitlements",
                 "/v1/results/figures", "/v1/methodology/assumptions", "/v1/overview/v2", "/v1/audit", "/v1/paper/preview"):
        r = client.get(path)
        assert r.status_code == 200, path + " " + r.text[:300]
    kr = client.get("/v1/fixed-income/key-rates").json()
    row = kr["rows"][2]
    assert abs(row["sum_krd"] - row["parallel_effective_duration"]) < 0.05
    assert client.post("/v1/data/refresh?group=wrds").status_code == 403
