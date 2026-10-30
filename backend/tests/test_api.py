"""API smoke tests on synthetic fixtures (no WRDS data in CI)."""
import time

from fastapi.testclient import TestClient

from lifecycle.api.main import app

client = TestClient(app)


def _wait(run_id: str, timeout: float = 300.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get("/v1/experiments/" + run_id).json()
        if s["status"] in ("done", "failed", "cancelled"):
            return s
        time.sleep(0.3)
    raise TimeoutError(run_id)


def test_catalog_and_market():
    r = client.get("/v1/catalog/series")
    assert r.status_code == 200
    body = r.json()
    for key in ["run_id", "spec_hash", "catalog_hash", "engine_version", "generated_at"]:
        assert key in body
    assert body["synthetic"] is True
    assert client.get("/v1/market/returns/summary?universe=core").status_code == 200
    assert client.get("/v1/market/regimes?universe=core&k=2").status_code == 200


def test_experiment_cache_and_results():
    spec = {"scenario": {"n_paths": 300, "n_train_paths": 200}, "policy": {"type": "glidepath"}}
    r = client.post("/v1/experiments", json=spec).json()
    s = _wait(r["run_id"])
    assert s["status"] == "done", s.get("error")
    res = client.get("/v1/experiments/" + r["run_id"] + "/results").json()["results"]
    assert res["ce"]["policy"]["ce"] > 0
    assert "delta" in res["ce"]
    again = client.post("/v1/experiments", json=spec).json()
    assert again["run_id"] == r["run_id"] and again["status"] == "done"
    for fmt in ["csv", "bibtex", "json", "pdf"]:
        assert client.get("/v1/reports/" + r["run_id"] + "?format=" + fmt).status_code == 200


def test_problem_details_for_unknown_run():
    r = client.get("/v1/experiments/doesnotexist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")


def test_small_sweep_and_compare():
    sweep = {"base": {"scenario": {"n_paths": 200, "n_train_paths": 150}}, "withdrawal_rates": [0.03, 0.05],
             "years_relative": [0, 5], "optimizer": "best_constant"}
    r = client.post("/v1/sweeps", json=sweep).json()
    s = _wait(r["sweep_id"], 600)
    assert s["status"] == "done", s.get("error")
    surf = client.get("/v1/sweeps/" + r["sweep_id"] + "/surface").json()["surface"]
    assert len(surf["cells"]) == 2 and len(surf["cells"][0]) == 2
    cell = surf["cells"][0][0]["run_id"]
    assert client.get("/v1/experiments/" + cell + "/results").status_code == 200
    a = client.post("/v1/experiments", json={"scenario": {"n_paths": 200}, "policy": {"type": "sixty_forty"}}).json()
    b = client.post("/v1/experiments", json={"scenario": {"n_paths": 200}, "policy": {"type": "target_date"}}).json()
    _wait(a["run_id"])
    _wait(b["run_id"])
    c = client.post("/v1/compare", json={"run_ids": [a["run_id"], b["run_id"]]}).json()
    s = _wait(c["run_id"])
    assert s["status"] == "done", s.get("error")
    res = client.get("/v1/compare/" + c["run_id"]).json()["results"]
    assert len(res["pairs"]) == 1
