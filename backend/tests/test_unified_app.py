"""Unified-application contracts: front-end research context → valid study specs, one run registry with
accounting semantics for every kind, and compatibility checks that refuse to pair runs from different engines."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lifecycle.api.main import app
from lifecycle.api.routers.v2 import HOLDINGS, TARGET_WEIGHT, semantics
from lifecycle.config import engine_version
from lifecycle.runs import registry
from lifecycle.studies import registry as studies

client = TestClient(app)
FIXTURE = Path(__file__).parent / "fixtures" / "context_specs.json"


def test_context_spec_fixture_is_current():
    # written by web/tests/unit/research-context.test.ts (file snapshot): both sides test the same JSON
    specs = json.loads(FIXTURE.read_text())
    assert {k.split(":")[0] for k in specs} == set(studies.studies())


@pytest.mark.parametrize("key", sorted(json.loads(FIXTURE.read_text())))
def test_context_specs_validate_against_strict_models(key):
    kind = key.split(":")[0]
    spec = json.loads(FIXTURE.read_text())[key]
    obj = studies.spec_model(kind).model_validate(spec)   # extra="forbid": unknown fields fail here
    assert obj.model_dump(mode="json")


def test_semantics_cover_every_kind():
    for kind in ("experiment", "sweep", "compare", "validation", "attribution"):
        assert semantics(kind) == TARGET_WEIGHT
    for kind in studies.studies():
        assert semantics(kind) in (HOLDINGS, "derived_from_runs")
    assert semantics("evidence") == "derived_from_runs"


def _fake(run_id: str, kind: str, spec: dict) -> None:
    registry.create(run_id, kind, json.dumps(spec), run_id, "cat-test", engine_version(), "lock-test")
    registry.update(run_id, status="done", stage="done", progress=1.0)


def test_unified_registry_lists_every_family_with_semantics():
    _fake("u" * 64, "experiment", {"scenario": {"generator": "bootstrap"}})
    _fake("v" * 64, "rebalance", {"scenario": {"generator": "bootstrap"}})
    body = client.get("/v1/runs?limit=500").json()
    by_id = {r["run_id"]: r for r in body["runs"]}
    assert by_id["u" * 64]["semantics"] == TARGET_WEIGHT and by_id["u" * 64]["family"] == "experiment"
    assert by_id["v" * 64]["semantics"] == HOLDINGS and by_id["v" * 64]["family"] == "study"
    assert by_id["v" * 64]["page"] == "/rebalance"
    studies_only = client.get("/v1/runs?family=study&limit=500").json()["runs"]
    assert all(r["family"] == "study" for r in studies_only)
    assert client.get("/v1/runs?family=bogus").status_code == 422
    assert client.get("/v1/runs/" + "u" * 64 + "/inspect").json()["semantics"] == TARGET_WEIGHT


def test_compatibility_refuses_cross_engine_pairs():
    _fake("w" * 64, "experiment", {"scenario": {"generator": "bootstrap"}})
    _fake("x" * 64, "rebalance", {"scenario": {"generator": "bootstrap"}})
    r = client.get("/v1/runs/compatibility", params={"a": "w" * 64, "b": "x" * 64}).json()
    assert r["compatible"] is False and r["paired_comparison_possible"] is False
    assert any("accounting semantics" in x for x in r["reasons"])
    same = client.get("/v1/runs/compatibility", params={"a": "w" * 64, "b": "u" * 64}).json()
    assert not any("accounting semantics" in x for x in same["reasons"])
