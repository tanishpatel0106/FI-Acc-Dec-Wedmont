import numpy as np
from fastapi import APIRouter, Query
from fastapi.responses import Response

from lifecycle.api.common import Problem, envelope, run_row_or_404
from lifecycle.data import panel
from lifecycle.research.hypotheses import HypothesesSpec
from lifecycle.runs import executor, registry
from lifecycle.runs.spec import AttributionSpec, CompareSpec, SweepSpec, ValidationSpec

router = APIRouter(prefix="/v1", tags=["sweeps, comparison, validation, reports"])


def _job_response(kind: str, spec, label: str | None = None, force: bool = False) -> dict:
    rid, status = executor.submit(kind, spec, label, force)
    row = registry.get(rid) or {}
    payload = {"status": status, "kind": kind}
    if status == "done":
        payload["results"] = registry.load_results(rid)
    return envelope(payload, rid, row.get("spec_hash"), row.get("catalog_hash"))


@router.post("/sweeps")
def submit_sweep(spec: SweepSpec, force: bool = False) -> dict:
    from lifecycle.runs.hashing import run_id_for
    from lifecycle.runs.sweeps import cell_specs

    rid, status = executor.submit("sweep", spec, spec.label, force)
    cells, xs, ys, _, _ = cell_specs(executor.with_catalog(spec))
    cell_ids = [[run_id_for("experiment", executor.with_catalog(c)) for c in row] for row in cells]
    row = registry.get(rid) or {}
    return envelope({"status": status, "sweep_id": rid, "cell_run_ids": cell_ids, "x": xs, "y": ys}, rid,
                    row.get("spec_hash"), row.get("catalog_hash"))


@router.get("/sweeps")
def list_sweeps(limit: int = 100) -> dict:
    rows = registry.list_runs("sweep", limit)
    for r in rows:
        full = registry.get(r["run_id"]) or {}
        r["spec"] = full.get("spec")
    return envelope({"sweeps": rows})


@router.get("/sweeps/disagreement")
def sweep_disagreement(ids: str, benchmark: str = "sixty_forty") -> dict:
    """Cells where generators (or other sweep variants) disagree on the sign of Delta_CE."""
    sweep_ids = [s for s in ids.split(",") if s]
    mats = []
    labels = []
    shape = None
    for sid in sweep_ids:
        res = registry.load_results(sid)
        if res is None:
            raise Problem(404, "Sweep results missing", sid)
        m = np.array(res["matrices"][benchmark]["delta"], dtype=float)
        se = np.array(res["matrices"][benchmark]["se"], dtype=float)
        if shape is None:
            shape = m.shape
            x, y = res["x"], res["y"]
        elif m.shape != shape:
            raise Problem(400, "Sweeps have different grids")
        mats.append(np.where(np.abs(m) > 2 * se, np.sign(m), 0.0))
        labels.append(res["summary"].get("generator"))
    arr = np.array(mats)
    pos = (arr > 0).sum(axis=0)
    neg = (arr < 0).sum(axis=0)
    disagree = (pos > 0) & (neg > 0)
    return envelope({"x": x, "y": y, "generators": labels, "disagree": disagree.tolist(),
                     "n_positive": pos.tolist(), "n_negative": neg.tolist(), "benchmark": benchmark})


@router.get("/sweeps/{sweep_id}/surface")
def sweep_surface(sweep_id: str) -> dict:
    row = run_row_or_404(sweep_id)
    if row["kind"] != "sweep":
        raise Problem(400, "Not a sweep")
    payload = {"status": row["status"], "stage": row["stage"], "progress": row["progress"], "spec": row["spec"]}
    if row["status"] == "done":
        payload["surface"] = registry.load_results(sweep_id)
    return envelope(payload, sweep_id, row["spec_hash"], row["catalog_hash"])


@router.post("/compare")
def compare(spec: CompareSpec) -> dict:
    return _job_response("compare", spec)


@router.get("/compare/{run_id}")
def compare_result(run_id: str) -> dict:
    row = run_row_or_404(run_id)
    payload = {"status": row["status"], "stage": row["stage"], "progress": row["progress"], "error": row["error"]}
    if row["status"] == "done":
        payload["results"] = registry.load_results(run_id)
    return envelope(payload, run_id, row["spec_hash"], row["catalog_hash"])


@router.get("/attribution/{sweep_id}")
def attribution(sweep_id: str, universe: str = "modern", by_regime: bool = True, n_paths: int = 1000) -> dict:
    run_row_or_404(sweep_id)
    return _job_response("attribution", AttributionSpec(sweep_id=sweep_id, universe=universe, by_regime=by_regime,
                                                        n_paths=n_paths))


@router.get("/validation/{run_id}")
def validation(run_id: str, n_param_boot: int = Query(20, le=500), max_paths: int = Query(10000, le=50000)) -> dict:
    run_row_or_404(run_id)
    counts = tuple(c for c in (1000, 2500, 5000, 10000, 50000) if c <= max_paths)
    return _job_response("validation", ValidationSpec(run_id=run_id, n_param_boot=n_param_boot, path_counts=counts))


@router.get("/reports/{run_id}")
def report(run_id: str, format: str = "pdf") -> Response:
    row = run_row_or_404(run_id)
    if row["status"] != "done":
        raise Problem(409, "Run not finished")
    from lifecycle.reports.builder import bundle

    data, media, name = bundle(run_id, format)
    return Response(content=data, media_type=media, headers={"Content-Disposition": "attachment; filename=" + name,
                                                             "X-Run-Id": run_id,
                                                             "X-Catalog-Hash": row["catalog_hash"] or ""})


@router.post("/research/hypotheses")
def run_hypotheses(spec: HypothesesSpec) -> dict:
    return _job_response("hypotheses", spec)


@router.get("/research/hypotheses")
def latest_hypotheses() -> dict:
    runs = registry.list_runs("hypotheses", 20)
    for r in runs:
        if r["status"] == "done":
            return envelope({"status": "done", "results": registry.load_results(r["run_id"])}, r["run_id"],
                            r["spec_hash"], r["catalog_hash"])
    if runs:
        r = runs[0]
        return envelope({"status": r["status"], "progress": r["progress"]}, r["run_id"], r["spec_hash"])
    return envelope({"status": "none"})


@router.get("/overview")
def overview() -> dict:
    meta = panel.meta()
    sweeps = registry.list_runs("sweep", 100)
    latest = {}
    # headline exhibits: prefer the parametric (optimised) policy on the core universe, then recency
    done = [s for s in sweeps if s["status"] == "done" and s.get("summary")]
    done.sort(key=lambda s: (s["summary"].get("optimizer") == "parametric", s["summary"].get("universe") == "core",
                             s["summary"].get("generator") == "bootstrap", s["created_at"]), reverse=True)
    for s in done:
        kind = s["summary"].get("kind")
        if kind not in latest:
            latest[kind] = {"sweep_id": s["run_id"], **s["summary"], "created_at": s["created_at"]}
    counts = {}
    for k in ["experiment", "sweep", "compare", "validation", "attribution", "hypotheses"]:
        counts[k] = len(registry.list_runs(k, 500, include_children=(k == "experiment")))
    return envelope({"as_of": panel.as_of(), "built_at": meta.get("built_at"), "synthetic": bool(meta.get("synthetic")),
                     "latest_sweeps": latest, "counts": counts,
                     "wrds": any(str(x).startswith("wrds:") for x in panel.catalog()["source"])})
