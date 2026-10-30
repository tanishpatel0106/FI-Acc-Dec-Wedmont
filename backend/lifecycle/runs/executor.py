"""Job submission and execution. In-process thread pool in dev; arq workers on Redis when REDIS_URL is set.

Lifecycle: queued -> generating_scenarios -> simulating -> optimising -> summarising -> done | failed | cancelled.
Progress is written to the registry, which the SSE endpoint polls, so it works across processes.
"""
import os
import threading
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic import BaseModel

from lifecycle.config import engine_version, lockfile_hash
from lifecycle.data import panel
from lifecycle.runs import registry
from lifecycle.runs.hashing import canonical_json, run_id_for, spec_hash

_POOL = ThreadPoolExecutor(max_workers=int(os.environ.get("LIFECYCLE_WORKERS", "1")))
_CANCEL: set[str] = set()
_ACTIVE: set[str] = set()
_ALOCK = threading.Lock()


class Cancelled(Exception):
    pass


def _job_fn(kind: str) -> Callable[[Any, Callable[[str, float], None], str], dict[str, Any]]:
    if kind == "experiment":
        from lifecycle.runs.experiment import run_experiment

        return lambda spec, prog, rid: run_experiment(spec, prog)
    if kind == "sweep":
        from lifecycle.runs.sweeps import run_sweep

        return run_sweep
    if kind == "compare":
        from lifecycle.runs.compare import run_compare

        return lambda spec, prog, rid: run_compare(spec, prog)
    if kind == "validation":
        from lifecycle.runs.validation import run_validation

        return lambda spec, prog, rid: run_validation(spec, prog)
    if kind == "attribution":
        from lifecycle.runs.attribution_job import run_attribution

        return lambda spec, prog, rid: run_attribution(spec, prog)
    if kind == "hypotheses":
        from lifecycle.research.hypotheses import run_hypotheses

        return lambda spec, prog, rid: run_hypotheses(spec, prog)
    raise ValueError("unknown job kind: " + kind)


def _spec_model(kind: str, spec_json: dict[str, Any]) -> BaseModel:
    from lifecycle.research.hypotheses import HypothesesSpec
    from lifecycle.runs.spec import AttributionSpec, CompareSpec, ExperimentSpec, SweepSpec, ValidationSpec

    model = {"experiment": ExperimentSpec, "sweep": SweepSpec, "compare": CompareSpec, "validation": ValidationSpec,
             "attribution": AttributionSpec, "hypotheses": HypothesesSpec}[kind]
    return model.model_validate(spec_json)


def with_catalog(spec: BaseModel) -> BaseModel:
    """Stamp the current catalog hash into experiment-like specs so a data change yields a new run ID."""
    from lifecycle.runs.spec import ExperimentSpec, SweepSpec

    chash = panel.catalog_hash()
    if isinstance(spec, ExperimentSpec):
        return spec.model_copy(update={"data": spec.data.model_copy(update={"catalog_hash": chash})})
    if isinstance(spec, SweepSpec):
        base = spec.base.model_copy(update={"data": spec.base.data.model_copy(update={"catalog_hash": chash})})
        return spec.model_copy(update={"base": base})
    return spec


def register(kind: str, spec: BaseModel, label: str | None = None, parent_id: str | None = None) -> str:
    spec = with_catalog(spec)
    rid = run_id_for(kind, spec)
    if registry.get(rid) is None:
        registry.create(rid, kind, canonical_json(spec), spec_hash(spec), panel.catalog_hash(), engine_version(),
                        lockfile_hash(), label, parent_id)
    return rid


def submit(kind: str, spec: BaseModel, label: str | None = None, force: bool = False) -> tuple[str, str]:
    """Returns (run_id, status). Identical specs hit the cache and return 'done' immediately."""
    rid = register(kind, spec, label)
    row = registry.get(rid)
    assert row is not None
    if row["status"] == "done" and not force and registry.load_results(rid) is not None:
        return rid, "done"
    with _ALOCK:
        if rid in _ACTIVE:
            return rid, row["status"]
        _ACTIVE.add(rid)
    registry.reset(rid)
    redis = os.environ.get("REDIS_URL", "")
    if redis != "":
        from lifecycle.workers.arq_worker import enqueue

        enqueue(rid)
    else:
        _POOL.submit(execute, rid)
    return rid, "queued"


def cancel(run_id: str) -> None:
    _CANCEL.add(run_id)


def execute(run_id: str) -> None:
    row = registry.get(run_id)
    if row is None:
        return
    kind = row["kind"]
    spec = _spec_model(kind, row["spec"])
    t0 = time.time()
    registry.update(run_id, status="running", stage="generating_scenarios", progress=0.01, started_at=registry.now())

    def progress(stage: str, frac: float) -> None:
        if run_id in _CANCEL:
            raise Cancelled()
        registry.update(run_id, stage=stage, progress=float(min(max(frac, 0.0), 0.99)))

    try:
        results = _job_fn(kind)(spec, progress, run_id)
        results["meta"] = meta_for(run_id)
        registry.save_results(run_id, results)
        summary = summary_of(kind, results)
        registry.update(run_id, status="done", stage="done", progress=1.0, finished_at=registry.now(),
                        timings={"wall_seconds": time.time() - t0, **results.get("timings", {})},
                        warnings=results.get("warnings", []), summary=summary)
    except Cancelled:
        registry.update(run_id, status="cancelled", stage="cancelled", finished_at=registry.now())
    except Exception as exc:
        registry.update(run_id, status="failed", stage="failed", finished_at=registry.now(),
                        error=str(exc) + "\n" + traceback.format_exc()[-4000:])
    finally:
        _CANCEL.discard(run_id)
        with _ALOCK:
            _ACTIVE.discard(run_id)


def run_sync(kind: str, spec: BaseModel, label: str | None = None, force: bool = False) -> str:
    """Execute in the calling thread (CLI, tests, sweeps of child cells)."""
    rid = register(kind, spec, label)
    row = registry.get(rid)
    assert row is not None
    if row["status"] == "done" and not force and registry.load_results(rid) is not None:
        return rid
    registry.reset(rid)
    execute(rid)
    return rid


def meta_for(run_id: str) -> dict[str, Any]:
    row = registry.get(run_id) or {}
    return {"run_id": run_id, "spec_hash": row.get("spec_hash"), "catalog_hash": row.get("catalog_hash"),
            "engine_version": row.get("engine_version", engine_version()), "lock_hash": row.get("lock_hash"),
            "generated_at": registry.now()}


def summary_of(kind: str, results: dict[str, Any]) -> dict[str, Any]:
    if kind == "experiment":
        ce = results.get("ce", {})
        out = {"ce": ce.get("policy", {}).get("ce"), "policy": results.get("policy", {}).get("label")}
        if "delta" in ce:
            out["delta"] = ce["delta"]["delta"]
            out["delta_se"] = ce["delta"]["se"]
        sf = results.get("shortfall")
        if sf:
            out["p_depletion"] = sf.get("p_depletion")
        return out
    if kind == "sweep":
        return results.get("summary", {})
    return {k: v for k, v in results.get("summary", {}).items()} if isinstance(results.get("summary"), dict) else {}
