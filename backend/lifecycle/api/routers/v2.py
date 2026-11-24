"""v2 research routes: studies (frontier, signed flow, PP, rebalancing, scenarios, as-of, optimise, compare,
evidence), market state, fixed income, data coverage/rights, run inspection, figures and methodology.

Every study is an idempotent POST keyed by its canonical spec hash. `submit=false` only looks up whether
the run exists, so pages never launch expensive Monte Carlo on view.
"""
import csv
import io
import json
import re
import threading
from typing import Any

from fastapi import APIRouter, Body, Query
from fastapi.responses import PlainTextResponse, Response

from lifecycle.api.common import Problem, envelope, run_row_or_404
from lifecycle.config import REPO_ROOT, engine_version, lockfile_hash
from lifecycle.data import panel
from lifecycle.runs import executor, registry
from lifecycle.runs.hashing import run_id_for
from lifecycle.studies import registry as studies

router = APIRouter(prefix="/v1", tags=["v2 research"])


def _study_model(kind: str):
    if not studies.is_study(kind):
        raise Problem(404, "Unknown study", kind + " is not a v2 study kind (%s)" % ", ".join(studies.studies()))
    return studies.spec_model(kind)


def _study_payload(kind: str, rid: str, status: str) -> dict:
    row = registry.get(rid) or {}
    payload: dict[str, Any] = {"status": row.get("status", status), "stage": row.get("stage"),
                               "progress": row.get("progress"), "kind": kind, "error": row.get("error"),
                               "spec": row.get("spec"), "created_at": row.get("created_at"),
                               "finished_at": row.get("finished_at"), "page": studies.studies()[kind]["page"],
                               "experiments": studies.studies()[kind]["experiments"]}
    if payload["status"] == "done":
        payload["results"] = registry.load_results(rid)
    return envelope(payload, rid, row.get("spec_hash"), row.get("catalog_hash"))


@router.get("/studies")
def list_studies() -> dict:
    out = []
    for kind, info in studies.studies().items():
        latest = next((r for r in registry.list_runs(kind, 20) if r["status"] == "done"), None)
        out.append({"kind": kind, "page": info["page"], "experiments": info["experiments"], "figure": info["figure"],
                    "latest_done": latest["run_id"] if latest else None,
                    "latest_finished_at": latest["finished_at"] if latest else None,
                    "default_spec": info["spec"]().model_dump(mode="json")})
    return envelope({"studies": out})


@router.get("/studies/{kind}/defaults")
def study_defaults(kind: str) -> dict:
    return envelope({"kind": kind, "spec": _study_model(kind)().model_dump(mode="json"),
                     "schema": _study_model(kind).model_json_schema()})


@router.post("/studies/{kind}")
def submit_study(kind: str, spec: dict = Body(default_factory=dict), submit: bool = True, force: bool = False) -> dict:
    model = _study_model(kind)
    try:
        obj = model.model_validate(spec)
    except Exception as exc:
        raise Problem(422, "Invalid study spec", str(exc)[:2000]) from exc
    if not submit:
        rid = run_id_for(kind, executor.with_catalog(obj))
        if registry.get(rid) is None:
            return envelope({"status": "none", "kind": kind, "page": studies.studies()[kind]["page"]}, rid)
        return _study_payload(kind, rid, "none")
    rid, status = executor.submit(kind, obj, getattr(obj, "label", None), force)
    return _study_payload(kind, rid, status)


@router.get("/studies/{kind}/latest")
def latest_study(kind: str) -> dict:
    _study_model(kind)
    runs = registry.list_runs(kind, 30)
    done = next((r for r in runs if r["status"] == "done"), None)
    if done is not None:
        return _study_payload(kind, done["run_id"], "done")
    if runs:
        return _study_payload(kind, runs[0]["run_id"], runs[0]["status"])
    return envelope({"status": "none", "kind": kind, "page": studies.studies()[kind]["page"]})


@router.get("/studies/run/{run_id}")
def study_run(run_id: str) -> dict:
    row = run_row_or_404(run_id)
    if not studies.is_study(row["kind"]):
        raise Problem(400, "Not a v2 study", row["kind"])
    return _study_payload(row["kind"], run_id, row["status"])


@router.get("/studies/run/{run_id}/trace")
def study_trace(run_id: str, path: int = Query(0, ge=0, le=50_000), r: float | None = None, b: float | None = None,
                strategy: str | None = None, policy: str | None = None) -> dict:
    """Deterministic single-path ledger trace (trades, costs, flows) re-simulated from the stored spec."""
    row = run_row_or_404(run_id)
    kind = row["kind"]
    spec = studies.spec_model(kind).model_validate(row["spec"]) if studies.is_study(kind) else None
    if kind == "frontier":
        from lifecycle.studies.frontier import trace_cell

        out = trace_cell(spec, 0.04 if r is None else r, 0.4 if b is None else b, path)
    elif kind == "rebalance":
        from lifecycle.studies.rebalance import trace_strategy

        out = trace_strategy(spec, strategy or "browne_15_35", path)
    elif kind == "signed_flow":
        from lifecycle.studies.signed_flow import trace_persona

        out = trace_persona(spec, policy or "target_date", path)
    elif kind in ("permanent", "compare_v2"):
        out = _pp_trace(spec, policy or "pp_classic", path)
    else:
        raise Problem(400, "No path trace for this study kind", kind)
    registry.audit("api", "trace", run_id, "path=%d" % path)
    return envelope({"trace": out, "kind": kind}, run_id, row["spec_hash"], row["catalog_hash"])


def _pp_trace(spec, policy: str, path: int) -> dict:
    from lifecycle.studies import common as S
    from lifecycle.studies.frontier import trace_payload
    from lifecycle.studies.permanent import PermanentSpec, _policy_def, _sleeves

    if not isinstance(spec, PermanentSpec):
        spec = PermanentSpec(data=spec.data, investor=spec.investor)
    es = S.experiment_spec(spec.data, spec.scenario, spec.investor, spec.preferences)
    ten = S.get_tensor(es)
    ctx = S.get_context(es, ten, es.scenario.seed)
    w, strat, over = _policy_def(policy, spec, _sleeves(spec, ten.assets))
    o = S.run(ctx, S.weights_vector(w, ten.assets), S.strategy(strat, spec.costs, **over), rate=spec.withdrawal,
              record=True, trace=path)
    p = trace_payload(o, ctx, ten.assets, path)
    p["policy"] = policy
    p["rule"] = strat
    return p


@router.get("/studies/run/{run_id}/export")
def study_export(run_id: str, format: str = "json", block: str | None = None) -> Response:
    """Derived results only (no raw WRDS observations exist in study payloads)."""
    row = run_row_or_404(run_id)
    res = registry.load_results(run_id)
    if res is None:
        raise Problem(409, "Run not finished")
    meta = {"run_id": run_id, "kind": row["kind"], "spec_hash": row["spec_hash"], "catalog_hash": row["catalog_hash"],
            "engine_version": row["engine_version"], "licence": "derived aggregate statistics"}
    data = res.get(block, res) if block else res
    registry.audit("api", "export", run_id, format + (":" + block if block else ""))
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["# provenance", json.dumps(meta)])
        _flatten(w, data, "")
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=%s_%s.csv" % (row["kind"], run_id)})
    return Response(json.dumps({"provenance": meta, "data": data}, default=str), media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=%s_%s.json" % (row["kind"], run_id)})


def _flatten(w, obj, prefix: str, depth: int = 0) -> None:
    if depth > 6:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(w, v, prefix + "." + str(k) if prefix else str(k), depth + 1)
    elif isinstance(obj, list) and obj and all(isinstance(x, (int, float, str, bool)) or x is None for x in obj):
        w.writerow([prefix] + obj)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:500]):
            _flatten(w, v, "%s[%d]" % (prefix, i), depth + 1)
    else:
        w.writerow([prefix, obj])


# ---- brief-named aliases (section 12.4) ---------------------------------------------------------------------
ALIASES = {"frontier": "frontier", "signed-flow": "signed_flow", "permanent-portfolio": "permanent",
           "rebalance": "rebalance", "stress": "scenario_lab", "walk-forward": "evidence", "asof": "asof",
           "optimize": "optimize", "compare": "compare_v2"}


@router.post("/research/{alias}")
def research_alias_post(alias: str, spec: dict = Body(default_factory=dict), submit: bool = True) -> dict:
    if alias not in ALIASES:
        raise Problem(404, "Unknown research route", alias)
    return submit_study(ALIASES[alias], spec, submit)


@router.get("/research/{alias}/{run_id}")
def research_alias_get(alias: str, run_id: str) -> dict:
    if alias not in ALIASES:
        raise Problem(404, "Unknown research route", alias)
    return study_run(run_id)


@router.get("/research-v2/hypotheses")
def hypotheses_v2() -> dict:
    from lifecycle.studies.evidence import preregistration

    latest = latest_study("evidence")
    latest["preregistration"] = preregistration()
    return latest


@router.get("/research-v2/evidence/{run_id}")
def evidence_for(run_id: str) -> dict:
    row = run_row_or_404(run_id)
    res = registry.load_results(run_id) or {}
    warnings = row.get("warnings") or []
    grade = "not_computed" if row["status"] != "done" else ("invalid" if any("SYNTHETIC" in w for w in warnings)
                                                            else "diagnostic" if (res.get("n_paths") or 0) < 1000
                                                            else "conditional")
    return envelope({"status": row["status"], "warnings": warnings, "evidence_grade": grade,
                     "universe": res.get("universe"), "ci_method": res.get("ci_method"),
                     "oos": "train/test seed sets disjoint" if row["kind"] in ("signed_flow", "permanent", "optimize")
                     else None}, run_id, row["spec_hash"], row["catalog_hash"])


# ---- market state (page G) -------------------------------------------------------------------------------------
@router.get("/market-state/latest")
def market_latest() -> dict:
    from lifecycle import market_state

    return envelope({"ribbon": market_state.ribbon(), **market_state.market_view(None)})


@router.get("/market-state/ribbon")
def market_ribbon() -> dict:
    from lifecycle import market_state

    return envelope(market_state.ribbon())


@router.get("/market-state/audit")
def market_audit() -> dict:
    from lifecycle import market_state

    return envelope(market_state.refresh_audit())


@router.get("/market-state/pit")
def market_pit(series_id: str, as_of: str) -> dict:
    from lifecycle import market_state

    return envelope(market_state.release_pit(series_id, as_of))


@router.get("/market-state/curve")
def market_curve(as_of: str | None = None, kind: str = "nominal") -> dict:
    from lifecycle import market_state

    v = market_state.market_view(as_of)
    return envelope({"as_of": v["as_of"], "curve": v["curves"].get(kind), "kind": kind})


@router.get("/market-state/{as_of}")
def market_asof(as_of: str) -> dict:
    from lifecycle import market_state

    if not re.match(r"^\d{4}-\d{2}(-\d{2})?$", as_of):
        raise Problem(400, "as_of must be YYYY-MM or YYYY-MM-DD")
    try:
        return envelope(market_state.market_view(as_of))
    except IndexError as exc:
        raise Problem(404, "UnavailableAsOf", str(exc)) from exc


# ---- fixed income (page F) -------------------------------------------------------------------------------------
@router.get("/fixed-income/key-rates")
def fi_key_rates(date: str | None = None, withdrawal: float = 40_000.0, years: int = 30) -> dict:
    from lifecycle import fixed_income_v2 as F

    return envelope(F.key_rate_table(date, withdrawal, years))


@router.get("/fixed-income/twist")
def fi_twist(date: str | None = None) -> dict:
    from lifecycle import fixed_income_v2 as F

    return envelope(F.twist_grid(date))


@router.get("/fixed-income/taylor")
def fi_taylor(date: str | None = None) -> dict:
    from lifecycle import fixed_income_v2 as F

    return envelope(F.full_vs_taylor(date))


@router.get("/fixed-income/liability-gap")
def fi_liability(date: str | None = None, withdrawal: float = 40_000.0, years: int = 30, pension: float = 0.0,
                 mortality: bool = True, inflation_shift_bp: float = 100.0) -> dict:
    from lifecycle import fixed_income_v2 as F

    return envelope(F.liability_gap(date, withdrawal, years, pension, mortality, inflation_shift_bp))


@router.get("/fixed-income/ladder")
def fi_ladder(date: str | None = None, withdrawal: float = 40_000.0, years: int = 30, budget: float = 1_000_000.0) -> dict:
    from lifecycle import fixed_income_v2 as F

    return envelope(F.ladder(date, withdrawal, years, budget))


@router.get("/fixed-income/coloss")
def fi_coloss() -> dict:
    from lifecycle import fixed_income_v2 as F

    return envelope(F.coloss_panel())


@router.get("/fixed-income/credit")
def fi_credit() -> dict:
    from lifecycle import fixed_income_v2 as F

    return envelope({"spreads": F.spreads_history(), "surface": F.credit_surface()})


# ---- data (coverage, rights, vintages, refresh) -----------------------------------------------------------------
@router.get("/data/entitlements")
def data_entitlements() -> dict:
    from lifecycle.data import entitlements

    return envelope(entitlements.public_view())


@router.get("/data/coverage")
def data_coverage(universe: str | None = None) -> dict:
    from lifecycle.studies.evidence import coverage_audit

    out = coverage_audit()
    if universe:
        out["universes"] = {universe: out["universes"].get(universe)}
    return envelope(out)


@router.get("/data/vintages")
def data_vintages(series_id: str) -> dict:
    p = panel.panel()
    sub = p[p["series_id"] == series_id]
    if len(sub) == 0:
        raise Problem(404, "Unknown series", series_id)
    cat = panel.catalog()
    row = cat[cat["series_id"] == series_id].iloc[0].to_dict()
    lic = str(row.get("licence_class"))
    out = {"series_id": series_id, "catalog": row, "vintages": sorted({str(v)[:10] for v in sub["vintage"]}),
           "publication_lag_days": int((sub["available_from"] - sub["month_end"]).dt.days.median())}
    if lic != "wrds_restricted":
        tail = sub.sort_values("month_end").tail(24)
        out["recent_releases"] = [{"period": str(r.month_end.date()), "available_from": str(r.available_from.date())}
                                  for r in tail.itertuples()]
    else:
        out["recent_releases"] = "withheld: wrds_restricted (raw observations never leave the server)"
    return envelope(out)


_REFRESH: dict[str, Any] = {"running": False, "last": None}


@router.post("/data/refresh")
def data_refresh(group: str = "treasury_daily") -> dict:
    """Backend refresh job. Public groups only; WRDS refreshes run from the CLI on the authorised host."""
    if group not in ("treasury_daily", "public_snapshot"):
        raise Problem(403, "Refresh not allowed from the API", "WRDS ingestion is CLI-only on the authorised host")
    if _REFRESH["running"]:
        return envelope({"status": "running", "group": group})

    def job():
        _REFRESH["running"] = True
        try:
            if group == "treasury_daily":
                from lifecycle.data.ingest_treasury_daily import pull_treasury_daily

                _REFRESH["last"] = pull_treasury_daily()
            else:
                from lifecycle.data.ingest import run_all

                _REFRESH["last"] = run_all(include_wrds=False, offline=True)
                panel.reload()
        except Exception as exc:
            _REFRESH["last"] = {"error": str(exc)[:500]}
        finally:
            _REFRESH["running"] = False
            registry.audit("api", "data_refresh", None, group + ": " + json.dumps(_REFRESH["last"], default=str)[:300])

    threading.Thread(target=job, daemon=True).start()
    return envelope({"status": "queued", "group": group})


@router.get("/data/refresh")
def data_refresh_status() -> dict:
    return envelope({"running": _REFRESH["running"], "last": _REFRESH["last"]})


@router.get("/data/health")
def data_health() -> dict:
    meta = panel.meta()
    cat = panel.catalog()
    failed = [r for r in registry.list_runs(None, 200, include_children=True) if r["status"] == "failed"][:30]
    audit_p = REPO_ROOT / "data" / "processed" / "ingest_audit.json"
    test_p = REPO_ROOT / "data" / "processed" / "test_report.json"
    return envelope({"built_at": meta.get("built_at"), "n_series": int(len(cat)), "catalog_hash": panel.catalog_hash(),
                     "series_with_gaps": cat[cat["n_missing"] > 0]["series_id"].tolist(),
                     "model_generated": cat[cat["provenance"] == "model_generated"]["series_id"].tolist(),
                     "failed_runs": [{"run_id": r["run_id"], "kind": r["kind"], "error": (r.get("error") or "")[:300]}
                                     for r in failed],
                     "ingest_audit": json.loads(audit_p.read_text())[-10:] if audit_p.exists() else [],
                     "tests": json.loads(test_p.read_text()) if test_p.exists() else None})


# ---- runs: inspection, compatibility, audit, reproduce, figures, paper ------------------------------------------
# Accounting semantics of each run kind. The two engines are kept side by side (nothing is re-computed or
# silently converted); every run reports which one produced it, and comparisons across them are flagged.
TARGET_WEIGHT = "target_weight_kernel"   # original monthly kernel: target weights, proportional turnover cost
HOLDINGS = "holdings_ledger"             # research-study kernel: executed-notional holdings ledger
DERIVED = "derived_from_runs"            # aggregates other persisted runs (no own simulation)
_SEMANTICS = {"experiment": TARGET_WEIGHT, "sweep": TARGET_WEIGHT, "compare": TARGET_WEIGHT, "validation": TARGET_WEIGHT,
              "attribution": TARGET_WEIGHT, "hypotheses": DERIVED, "evidence": DERIVED}


def semantics(kind: str) -> str:
    """Accounting semantics recorded for a run kind (studies other than evidence use the holdings ledger)."""
    if kind in _SEMANTICS:
        return _SEMANTICS[kind]
    return HOLDINGS if studies.is_study(kind) else "unknown"


@router.get("/runs")
def list_all_runs(kind: str | None = None, status: str | None = None, family: str | None = Query(None, pattern="^(study|experiment)$"),
                  limit: int = Query(200, ge=1, le=2000)) -> dict:
    """One registry for every run kind (experiments, sweeps, comparisons, validations, attributions,
    hypotheses and the nine studies), each with its accounting semantics and page."""
    rows = registry.list_runs(kind, limit)
    out = []
    for r in rows:
        if status and r["status"] != status:
            continue
        is_study = studies.is_study(r["kind"])
        if family == "study" and not is_study:
            continue
        if family == "experiment" and is_study:
            continue
        out.append({**r, "semantics": semantics(r["kind"]), "family": "study" if is_study else "experiment",
                    "page": studies.studies()[r["kind"]]["page"] if is_study else _EXPERIMENT_PAGE.get(r["kind"])})
    return envelope({"runs": out, "semantics": {TARGET_WEIGHT: "monthly target-weight kernel (Simulator, policy family, CE sweeps)",
                                                HOLDINGS: "executed-notional holdings ledger (research studies)",
                                                DERIVED: "aggregates persisted runs"}})


_EXPERIMENT_PAGE = {"experiment": "/lifecycle-flows?section=simulator", "sweep": "/withdrawal-lab?section=utility",
                    "compare": "/compare?section=saved-runs", "validation": "/research?section=validation",
                    "attribution": "/optimize?section=attribution", "hypotheses": "/research?section=hypotheses"}


@router.get("/runs/{run_id}/inspect")
def run_inspect(run_id: str) -> dict:
    row = run_row_or_404(run_id)
    res = registry.load_results(run_id) or {}
    spec = row.get("spec") or {}
    seeds = {}
    sc = spec.get("scenario") or spec.get("base", {}).get("scenario") or {}
    if sc:
        seeds = {"evaluation_seed": sc.get("seed"), "training_seed": "SeedSequence([seed, 1]) (disjoint)"}
    uni = res.get("universe") or {}
    return envelope({"kind": row["kind"], "status": row["status"], "spec": spec, "seeds": seeds,
                     "lock_hash": row.get("lock_hash"), "engine_version": row.get("engine_version"),
                     "catalog_hash": row.get("catalog_hash"), "warnings": row.get("warnings"),
                     "timings": row.get("timings"), "universe": uni,
                     "data_class": uni.get("data_class") if isinstance(uni, dict) else None,
                     "raw_or_derived": "derived (aggregates and quantiles only)",
                     "reproduce": "python -m lifecycle.cli reproduce " + run_id, "parent_id": row.get("parent_id"),
                     "semantics": semantics(row["kind"]),
                     "created_at": row.get("created_at"), "finished_at": row.get("finished_at"),
                     "audit": registry.audit_log(50, run_id)}, run_id, row["spec_hash"], row["catalog_hash"])


@router.get("/runs/compatibility")
def run_compatibility(a: str, b: str) -> dict:
    ra, rb = run_row_or_404(a), run_row_or_404(b)
    sa, sb = ra.get("spec") or {}, rb.get("spec") or {}
    reasons = []
    if ra["kind"] != rb["kind"]:
        reasons.append("different run kinds (%s vs %s)" % (ra["kind"], rb["kind"]))
    sem_a, sem_b = semantics(ra["kind"]), semantics(rb["kind"])
    if sem_a != sem_b:
        reasons.append("different accounting semantics (%s vs %s): the runs come from different engines and "
                       "cannot be paired" % (sem_a, sem_b))
    if ra.get("catalog_hash") != rb.get("catalog_hash"):
        reasons.append("different data catalogs (%s vs %s): recalibrate both on the same vintage" % (
            ra.get("catalog_hash"), rb.get("catalog_hash")))

    def g(s, *ks):
        for k in ks:
            s = (s or {}).get(k) if isinstance(s, dict) else None
        return s
    for lab, keys in (("universe", ("data", "universe")), ("generator", ("scenario", "generator")),
                      ("n_paths", ("scenario", "n_paths")), ("seed", ("scenario", "seed")),
                      ("horizon", ("investor", "horizon_years")), ("max_age", ("investor", "max_age")),
                      ("gamma", ("preferences", "gamma")), ("spending rule", ("policy", "spending_rule")),
                      ("withdrawal", ("policy", "withdrawal_rate"))):
        va, vb = g(sa, *keys), g(sb, *keys)
        if va != vb and (va is not None or vb is not None):
            reasons.append("%s differs (%s vs %s)" % (lab, va, vb))
    paired = not any(r.split(" ")[0] in ("universe", "generator", "seed", "n_paths") for r in reasons)
    return envelope({"compatible": len(reasons) == 0, "paired_comparison_possible": paired and ra["kind"] == rb["kind"] and sem_a == sem_b,
                     "semantics": [sem_a, sem_b],
                     "reasons": reasons, "remedy": "submit a paired re-run with identical data, scenario and spending"
                     if reasons else None})


@router.get("/audit")
def audit(limit: int = Query(200, le=2000), run_id: str | None = None) -> dict:
    return envelope({"events": registry.audit_log(limit, run_id), "note": "no credentials are recorded"})


FIGURES = [
    ("F1", "Bond Necessity Frontier", "frontier", "/withdrawal-lab"),
    ("F2", "Signed-Net-Flow / Lifecycle Allocation Surface", "signed_flow", "/lifecycle-flows"),
    ("F3", "Permanent Portfolio Comparison", "permanent", "/permanent-portfolio"),
    ("F4", "Rebalancing Efficiency Frontier", "rebalance", "/rebalance"),
    ("F5", "Sequence-Risk and Shortfall Decomposition", "scenario_lab", "/scenarios"),
    ("F6", "Macro-Regime / Model Robustness", "evidence", "/research"),
]


@router.get("/results/figures")
def figures() -> dict:
    out = []
    for fid, title, kind, page in FIGURES:
        runs = registry.list_runs(kind, 20)
        done = next((r for r in runs if r["status"] == "done"), None)
        last = runs[0] if runs else None
        grade = "not_computed"
        if done:
            res = registry.load_results(done["run_id"]) or {}
            warn = " ".join(res.get("warnings", []))
            grade = "invalid" if "SYNTHETIC" in warn else ("diagnostic" if (res.get("n_paths") or 2000) < 1000 else "conditional")
        out.append({"figure": fid, "title": title, "study": kind, "page": page,
                    "run_id": done["run_id"] if done else None, "finished_at": done["finished_at"] if done else None,
                    "status": done["status"] if done else (last["status"] if last else "not_computed"),
                    "failure": (registry.get(last["run_id"]) or {}).get("error", "")[:300] if last and last["status"] == "failed" else None,
                    "evidence_grade": grade,
                    "reproduce": ("python -m lifecycle.cli reproduce " + done["run_id"]) if done else
                    "python -m lifecycle.cli seed-v2 --only " + kind})
    return envelope({"figures": out})


@router.get("/results/manifest")
def manifest() -> dict:
    rows = []
    for kind in studies.studies():
        for r in registry.list_runs(kind, 50):
            rows.append({"kind": kind, "run_id": r["run_id"], "status": r["status"], "catalog_hash": r["catalog_hash"],
                         "engine_version": r["engine_version"], "finished_at": r["finished_at"],
                         "error": (r.get("error") or "")[:200] or None})
    return envelope({"runs": rows, "engine_version": engine_version(), "lock_hash": lockfile_hash()})


@router.post("/reports/build")
def reports_build(run_ids: list[str] = Body(default_factory=list)) -> dict:
    ids = run_ids or [f["run_id"] for f in figures()["figures"] if f["run_id"]]
    built = []
    for rid in ids:
        row = registry.get(rid)
        if row is None or row["status"] != "done":
            built.append({"run_id": rid, "status": "skipped", "reason": "not done"})
            continue
        built.append({"run_id": rid, "kind": row["kind"], "status": "ok",
                      "exports": {"json": "/v1/studies/run/%s/export?format=json" % rid,
                                  "csv": "/v1/studies/run/%s/export?format=csv" % rid,
                                  "pdf": "/v1/reports/%s?format=pdf" % rid if row["kind"] == "experiment" else None}})
    registry.audit("api", "report_build", None, ",".join(ids)[:400])
    return envelope({"manifest": built, "engine_version": engine_version(), "licence_check":
                     "exports contain derived aggregates only; WRDS raw rows are never written to study payloads"})


@router.get("/paper/preview")
def paper_preview() -> dict:
    import shutil

    tex = (REPO_ROOT / "paper" / "main.tex").read_text()
    figs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex)
    inputs = re.findall(r"\\(?:input|include)\{([^}]+)\}", tex)
    sections = re.findall(r"\\section\*?\{([^}]+)\}", tex)
    missing = []
    for f in figs:
        p = REPO_ROOT / "paper" / f
        if not any((p.parent / (p.name + ext)).exists() or p.exists() for ext in ("", ".pdf", ".png")):
            missing.append(f)
    bib = (REPO_ROOT / "paper" / "references.bib").read_text()
    keys = re.findall(r"@\w+\{([^,]+),", bib)
    cites = set(c.strip() for grp in re.findall(r"\\cite[tp]?\{([^}]+)\}", tex) for c in grp.split(","))
    run_ids = REPO_ROOT / "research" / "experiments" / "run_ids.json"
    return envelope({"sections": sections, "figures": figs, "missing_figures": missing, "inputs": inputs,
                     "bib_entries": len(keys), "cited": sorted(cites), "uncited": sorted(set(keys) - cites)[:50],
                     "undefined_citations": sorted(cites - set(keys)), "latexmk_available": shutil.which("latexmk") is not None,
                     "run_ids_file": run_ids.exists(),
                     "build": "make paper  (figures from research/experiments/run_ids.json, then latexmk if installed)"})


# ---- methodology (page M) --------------------------------------------------------------------------------------
@router.get("/methodology/assumptions")
def assumptions() -> dict:
    rows = []
    for kind, info in studies.studies().items():
        spec = info["spec"]().model_dump(mode="json")
        for path, v in _walk(spec):
            if path.startswith("data.catalog_hash") or path.endswith("label"):
                continue
            rows.append({"study": kind, "parameter": path, "default": v})
    decisions = [
        {"decision": "Timing", "value": "flows at the start of the month, trade, then earn R_{t+1}", "sensitivity": "n/a (contract)"},
        {"decision": "Utility floor", "value": "$3,000/yr enters utility only; never counted as funded", "sensitivity": "util_floor_annual"},
        {"decision": "Success", "value": "fixed-horizon financial; until-death reported separately", "sensitivity": "horizons_years"},
        {"decision": "Regime signal", "value": "Hamilton-filter prediction on the simulated path (lagged)", "sensitivity": "oracle shown as bound only"},
        {"decision": "Costs", "value": "commission + half spread on executed notional, quadratic slippage per $1m", "sensitivity": "cost grids in /rebalance"},
        {"decision": "Bond returns (public mode)", "value": "par bonds repriced from CMT yields (model_generated)", "sensitivity": "WRDS CRSP observed returns"},
        {"decision": "Gold", "value": "observed fund returns only (WRDS GLD); no public LBMA history ingested", "sensitivity": "pp_research_historical after rights review"},
        {"decision": "Mortality", "value": "SSA period life table, unisex", "sensitivity": "sex, mortality on/off"},
    ]
    return envelope({"defaults": rows, "decisions": decisions})


def _walk(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, prefix + "." + k if prefix else k)
    else:
        yield prefix, obj


@router.get("/methodology/bibliography")
def bibliography() -> dict:
    bib = (REPO_ROOT / "paper" / "references.bib").read_text()
    entries = []
    for m in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", bib, re.S):
        body = m.group(3)

        def f(name, body=body):
            mm = re.search(name + r"\s*=\s*[{\"](.+?)[}\"]\s*,?\s*\n", body, re.S)
            return re.sub(r"[{}]", "", mm.group(1)).strip() if mm else None
        entries.append({"type": m.group(1), "key": m.group(2).strip(), "title": f("title"), "author": f("author"),
                        "year": f("year"), "journal": f("journal"), "doi": f("doi"), "url": f("url")})
    return envelope({"entries": entries})


@router.get("/methodology/bibtex", response_class=PlainTextResponse)
def bibtex() -> str:
    return (REPO_ROOT / "paper" / "references.bib").read_text()


# ---- overview v2 (page A) ------------------------------------------------------------------------------------------
@router.get("/overview/v2")
def overview_v2() -> dict:
    latest = {}
    for kind in studies.studies():
        runs = registry.list_runs(kind, 20)
        done = next((r for r in runs if r["status"] == "done"), None)
        latest[kind] = {"run_id": done["run_id"] if done else None, "finished_at": done["finished_at"] if done else None,
                        "status": done["status"] if done else (runs[0]["status"] if runs else "not_computed"),
                        "summary": done.get("summary") if done else None}
    tiles = []
    fr = registry.load_results(latest["frontier"]["run_id"]) if latest["frontier"]["run_id"] else None
    if fr:
        mt, mh = fr["main_target"], fr["main_horizon"]
        key = "%d|%.2f" % (mh, mt)
        row5 = next((t for t in fr["thresholds"][key] if abs(t["r"] - 0.05) < 1e-9), None)
        boot5 = next((t for t in fr["threshold_bootstrap"].get(key, []) if abs(t["r"] - 0.05) < 1e-9), None)
        tiles.append({"id": "bond_threshold", "title": "Bond necessity at 5%% withdrawal (%dy, %.0f%% target)" % (mh, mt * 100),
                      "value": row5["b_min"] if row5 else None, "status": row5["status"] if row5 else "not_computed",
                      "ci": [boot5.get("q05"), boot5.get("q95")] if boot5 else None,
                      "benchmark": "all-equity", "universe": fr["universe"]["name"], "run_id": latest["frontier"]["run_id"],
                      "date": latest["frontier"]["finished_at"], "breakpoint": fr["breakpoints"].get("%.2f" % mt)})
    pp = registry.load_results(latest["permanent"]["run_id"]) if latest["permanent"]["run_id"] else None
    if pp:
        best = max((m for m in pp["scorecard"] if "delta_ce_vs_benchmark" in m),
                   key=lambda m: m["delta_ce_vs_benchmark"]["lo"], default=None)
        if best:
            d = best["delta_ce_vs_benchmark"]
            tiles.append({"id": "defensive_mix", "title": "Best-supported defensive mix vs %s" % pp["benchmark"],
                          "value": d["delta"], "label": best["label"], "ci": [d["lo"], d["hi"]], "status": "computed",
                          "universe": pp["universe"]["name"], "run_id": latest["permanent"]["run_id"],
                          "date": latest["permanent"]["finished_at"]})
    rb = registry.load_results(latest["rebalance"]["run_id"]) if latest["rebalance"]["run_id"] else None
    if rb:
        cands = [f for f in rb["frontier"] if "delta_ce" in f]
        best = max(cands, key=lambda f: f["delta_ce"]["lo"], default=None)
        if best:
            tiles.append({"id": "rebalancing", "title": "Best rebalancing rule vs %s (net of costs)" % rb["baseline"],
                          "value": best["delta_ce"]["delta"], "label": best["strategy"],
                          "ci": [best["delta_ce"]["lo"], best["delta_ce"]["hi"]], "status": "computed",
                          "universe": rb["universe"]["name"], "run_id": latest["rebalance"]["run_id"],
                          "date": latest["rebalance"]["finished_at"]})
    op = registry.load_results(latest["optimize"]["run_id"]) if latest["optimize"]["run_id"] else None
    if op:
        band = op["uncertainty_band"]["path_bootstrap"]
        tiles.append({"id": "ce_improvement", "title": "CE-optimal equity share at %.1f%% withdrawal" % (op["withdrawal"] * 100),
                      "value": op["base_equity"], "ci": [band["q05"], band["q95"]], "status": "computed",
                      "universe": op["universe"]["name"], "run_id": latest["optimize"]["run_id"],
                      "date": latest["optimize"]["finished_at"], "benchmark": "equity/10Y grid"})
    sf = registry.load_results(latest["signed_flow"]["run_id"]) if latest["signed_flow"]["run_id"] else None
    ev = registry.load_results(latest["evidence"]["run_id"]) if latest["evidence"]["run_id"] else None
    cat = panel.catalog()
    coverage = cat[["series_id", "source", "provenance", "licence_class", "first_obs", "last_obs"]].to_dict("records")
    timeline = []
    meta = panel.meta()
    timeline.append({"stage": "data panel built", "at": meta.get("built_at"), "detail": "catalog " + panel.catalog_hash()})
    test_p = REPO_ROOT / "data" / "processed" / "test_report.json"
    if test_p.exists():
        t = json.loads(test_p.read_text())
        timeline.append({"stage": "tests", "at": t.get("at"), "detail": "%s passed, %s failed" % (t.get("passed"), t.get("failed"))})
    else:
        timeline.append({"stage": "tests", "at": None, "detail": "no recorded run (python -m lifecycle.cli selftest)"})
    for kind, lab in (("frontier", "simulation: bond frontier"), ("signed_flow", "calibration/optimisation: signed flow"),
                      ("permanent", "simulation: permanent portfolio"), ("rebalance", "simulation: rebalancing"),
                      ("scenario_lab", "scenario diagnostics"), ("evidence", "validation: H1-H12")):
        timeline.append({"stage": lab, "at": latest[kind]["finished_at"], "detail": latest[kind]["status"],
                         "run_id": latest[kind]["run_id"]})
    return envelope({"tiles": tiles, "latest": latest, "frontier_mini": {
        "r": fr["r"], "b": fr["b"], "p": fr["p_success"][str(fr["main_horizon"])], "target": fr["main_target"],
        "agreement": fr["agreement"], "optima": fr["optima"], "run_id": latest["frontier"]["run_id"]} if fr else None,
        "continuum": {"q": sf["q"], "ages": sf["ages"], "b_ce": sf["b_ce"], "run_id": latest["signed_flow"]["run_id"]}
        if sf else None, "evidence": ev["evidence_matrix"] if ev else None,
        "hypotheses": [{k: h[k] for k in ("id", "verdict", "evidence_grade", "run_id")} for h in ev["hypotheses"]] if ev else None,
        "timeline": timeline, "coverage": coverage, "as_of": panel.as_of(), "synthetic": bool(meta.get("synthetic")),
        "wrds": any(str(x).startswith("wrds:") for x in cat["source"])})
