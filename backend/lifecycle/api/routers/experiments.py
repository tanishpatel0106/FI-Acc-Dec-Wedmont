import asyncio
import json

import numpy as np
import pyarrow as pa
from fastapi import APIRouter, Query
from fastapi.responses import Response, StreamingResponse

from lifecycle.api.common import Problem, envelope, run_row_or_404
from lifecycle.runs import executor, registry
from lifecycle.runs.spec import ExperimentSpec

router = APIRouter(prefix="/v1", tags=["experiments"])


def status_payload(row: dict) -> dict:
    return {"status": row["status"], "stage": row["stage"], "progress": row["progress"], "kind": row["kind"],
            "label": row.get("label"), "parent_id": row.get("parent_id"), "spec": row.get("spec"),
            "timings": row.get("timings"), "warnings": row.get("warnings"), "error": row.get("error"),
            "created_at": row.get("created_at"), "started_at": row.get("started_at"),
            "finished_at": row.get("finished_at"), "summary": row.get("summary"), "lock_hash": row.get("lock_hash")}


@router.post("/experiments")
def submit_experiment(spec: ExperimentSpec, label: str | None = None, force: bool = False) -> dict:
    rid, status = executor.submit("experiment", spec, label, force)
    row = registry.get(rid) or {}
    return envelope({"status": status}, rid, row.get("spec_hash"), row.get("catalog_hash"))


@router.get("/experiments")
def list_experiments(kind: str | None = None, limit: int = Query(100, le=500), parent_id: str | None = None,
                     include_children: bool = False) -> dict:
    return envelope({"runs": registry.list_runs(kind, limit, parent_id, include_children)})


@router.get("/experiments/{run_id}")
def get_experiment(run_id: str) -> dict:
    row = run_row_or_404(run_id)
    return envelope(status_payload(row), run_id, row["spec_hash"], row["catalog_hash"])


@router.post("/experiments/{run_id}/cancel")
def cancel_experiment(run_id: str) -> dict:
    row = run_row_or_404(run_id)
    executor.cancel(run_id)
    return envelope({"status": "cancelling"}, run_id, row["spec_hash"], row["catalog_hash"])


@router.get("/experiments/{run_id}/events")
async def experiment_events(run_id: str) -> StreamingResponse:
    run_row_or_404(run_id)

    async def stream():
        last = None
        idle = 0
        while True:
            row = registry.get(run_id)
            if row is None:
                break
            state = (row["stage"], round(float(row["progress"]), 3), row["status"])
            if state != last:
                last = state
                payload = {"run_id": run_id, "stage": row["stage"], "status": row["status"],
                           "fraction": row["progress"], "error": (row.get("error") or "")[:500]}
                yield "data: " + json.dumps(payload) + "\n\n"
                idle = 0
            else:
                idle += 1
                if idle % 30 == 0:
                    yield ": keep-alive\n\n"
            if row["status"] in ("done", "failed", "cancelled"):
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/experiments/{run_id}/results")
def experiment_results(run_id: str) -> dict:
    row = run_row_or_404(run_id)
    if row["status"] != "done":
        raise Problem(409, "Run not finished", "status is " + row["status"])
    res = registry.load_results(run_id)
    if res is None:
        raise Problem(404, "Results missing", "run is done but results were not found on disk")
    return envelope({"spec": row["spec"], "kind": row["kind"], "results": res}, run_id, row["spec_hash"],
                    row["catalog_hash"])


@router.get("/experiments/{run_id}/paths")
def experiment_paths(run_id: str, n: int = Query(200, le=2000)) -> Response:
    """Sample path arrays as Arrow IPC (application/vnd.apache.arrow.stream)."""
    row = run_row_or_404(run_id)
    if row["kind"] != "experiment":
        raise Problem(400, "Not an experiment")
    from lifecycle.runs.experiment import sample_paths

    spec = ExperimentSpec.model_validate(row["spec"])
    if spec.policy.type == "dp":
        raise Problem(400, "Path export is not available for DP runs")
    arrays = sample_paths(spec, n)
    N, Y1 = arrays["wealth"].shape
    ages = spec.investor.start_age + np.arange(Y1)
    cols = {"path": np.repeat(np.arange(N), Y1), "age": np.tile(ages, N),
            "wealth": arrays["wealth"].reshape(-1)}
    cons = np.concatenate([arrays["consumption"], np.full((N, 1), np.nan)], axis=1)
    cols["consumption"] = cons.reshape(-1)
    if "bench_wealth" in arrays:
        cols["bench_wealth"] = arrays["bench_wealth"].reshape(-1)
        bc = np.concatenate([arrays["bench_consumption"], np.full((N, 1), np.nan)], axis=1)
        cols["bench_consumption"] = bc.reshape(-1)
    table = pa.table(cols)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return Response(content=sink.getvalue().to_pybytes(), media_type="application/vnd.apache.arrow.stream",
                    headers={"X-Run-Id": run_id, "X-Spec-Hash": row["spec_hash"] or "",
                             "X-Catalog-Hash": row["catalog_hash"] or ""})
