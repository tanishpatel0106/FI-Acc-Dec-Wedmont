"""Command line: ingestion, seeding default exhibits, sweeps, reproduction and OpenAPI export.

    python -m lifecycle.cli ingest [--wrds] [--offline]
    python -m lifecycle.cli snapshot
    python -m lifecycle.cli build-panel
    python -m lifecycle.cli seed [--full]
    python -m lifecycle.cli reproduce RUN_ID
    python -m lifecycle.cli spec research/experiments/<file>.json
    python -m lifecycle.cli openapi out.json
"""
import argparse
import json
import sys
from pathlib import Path

from lifecycle.config import REPO_ROOT


def cmd_ingest(args: argparse.Namespace) -> None:
    from lifecycle.data.ingest import run_all

    run_all(include_wrds=args.wrds, offline=args.offline)


def cmd_snapshot(args: argparse.Namespace) -> None:
    from lifecycle.data.snapshot import create_snapshot

    m = create_snapshot()
    print("snapshot written for vintage", m["vintage"])


def cmd_build(args: argparse.Namespace) -> None:
    from lifecycle.data.normalize import build_panel

    print(json.dumps(build_panel(), indent=2)[:2000])


def _run_spec_file(path: Path) -> str:
    from lifecycle.research.hypotheses import HypothesesSpec
    from lifecycle.runs import executor
    from lifecycle.runs.spec import AttributionSpec, ExperimentSpec, SweepSpec

    doc = json.loads(path.read_text())
    kind = doc["kind"]
    model = {"experiment": ExperimentSpec, "sweep": SweepSpec, "attribution": AttributionSpec,
             "hypotheses": HypothesesSpec}[kind]
    spec = model.model_validate(doc["spec"])
    rid = executor.run_sync(kind, spec, doc.get("label"))
    from lifecycle.runs import registry

    row = registry.get(rid)
    print(path.name, "->", rid, row["status"] if row else "?", (row or {}).get("error") or "")
    return rid


def cmd_spec(args: argparse.Namespace) -> None:
    for p in args.paths:
        _run_spec_file(Path(p))


def cmd_seed(args: argparse.Namespace) -> None:
    """Run the versioned exhibit specs in research/experiments (core set, or everything with --full)."""
    folder = REPO_ROOT / "research" / "experiments"
    files = sorted(folder.glob("*.json"))
    ids = {}
    for f in files:
        doc = json.loads(f.read_text())
        if doc.get("tier", "core") != "core" and not args.full:
            continue
        if doc["kind"] in ("attribution", "hypotheses"):
            continue
        ids[f.stem] = _run_spec_file(f)
    # dependent jobs reference the headline sweep
    from lifecycle.research.hypotheses import HypothesesSpec
    from lifecycle.runs import executor
    from lifecycle.runs.spec import AttributionSpec

    head = ids.get("01_decumulation_core_bootstrap")
    if head is not None and args.full:
        att = executor.run_sync("attribution", AttributionSpec(sweep_id=head, universe="modern", n_paths=800))
        executor.run_sync("hypotheses", HypothesesSpec(sweep_id=head, attribution_id=att, n_boot=5))
    (REPO_ROOT / "research" / "experiments" / "run_ids.json").write_text(json.dumps(ids, indent=2))
    print("seeded:", json.dumps(ids, indent=2))


def cmd_reproduce(args: argparse.Namespace) -> None:
    """Re-execute a run from its stored spec and assert identical summary statistics."""
    from lifecycle.runs import executor, registry
    from lifecycle.runs.jsonsafe import clean

    row = registry.get(args.run_id)
    if row is None:
        sys.exit("unknown run " + args.run_id)
    before = registry.load_results(args.run_id)
    spec = executor._spec_model(row["kind"], row["spec"])
    fn = executor._job_fn(row["kind"])
    after = clean(fn(spec, lambda s, f: None, args.run_id))
    keys = ["ce", "shortfall", "terminal_wealth", "matrices", "conditions", "pairs"]
    from lifecycle.studies import registry as studies

    if studies.is_study(row["kind"]):
        # every derived block of a study must reproduce exactly (timings and run metadata excluded)
        keys = [k for k in (before or {}) if k not in ("timings", "meta")]
    ok = True
    for k in keys:
        if before is None or k not in before:
            continue
        a = json.dumps(before[k], sort_keys=True)
        b = json.dumps(clean(after.get(k)), sort_keys=True)
        same = a == b
        ok = ok and same
        print(("identical  " if same else "DIFFERENT  ") + k)
    if not ok:
        sys.exit(1)
    print("reproduced", args.run_id)


SEED_V2_ORDER = ("frontier", "signed_flow", "rebalance", "scenario_lab", "optimize", "compare_v2", "asof", "permanent",
                 "evidence")


def cmd_seed_v2(args: argparse.Namespace) -> None:
    """Run the default v2 studies (each a versioned, hashed run) and record their IDs in research/results."""
    from lifecycle.runs import executor, registry
    from lifecycle.studies import registry as studies

    out = {}
    kinds = [k for k in SEED_V2_ORDER if not args.only or k in args.only]
    for kind in kinds:
        model = studies.spec_model(kind)
        spec = model()
        if kind == "permanent" and args.pp_universe:
            from lifecycle.studies.common import StudyData

            spec = spec.model_copy(update={"data": StudyData(universe=args.pp_universe)})
        print("running", kind, "...", flush=True)
        rid = executor.run_sync(kind, spec, "default " + kind, force=args.force)
        row = registry.get(rid) or {}
        out[kind] = {"run_id": rid, "status": row.get("status"), "error": (row.get("error") or "").split("\n")[0][:400] or None,
                     "seconds": (row.get("timings") or {}).get("wall_seconds")}
        print("  ", kind, rid, row.get("status"), (row.get("error") or "")[:200], flush=True)
        if kind == "permanent" and row.get("status") == "failed" and not args.pp_universe:
            from lifecycle.studies.common import StudyData

            print("   permanent portfolio with gold unavailable; running the ex-gold variants on core_duration", flush=True)
            spec2 = spec.model_copy(update={"data": StudyData(universe="core_duration")})
            rid2 = executor.run_sync(kind, spec2, "permanent (core_duration, no gold)", force=args.force)
            row2 = registry.get(rid2) or {}
            out["permanent_core_duration"] = {"run_id": rid2, "status": row2.get("status"),
                                              "error": (row2.get("error") or "").split("\n")[0][:400] or None}
            print("  ", kind, rid2, row2.get("status"), flush=True)
    folder = REPO_ROOT / "research" / "results"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "v2_run_ids.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


def cmd_market_refresh(args: argparse.Namespace) -> None:
    from lifecycle.data.ingest_treasury_daily import pull_treasury_daily

    print(json.dumps(pull_treasury_daily(), indent=2))


def cmd_entitlements(args: argparse.Namespace) -> None:
    from lifecycle.data.entitlements import scan

    print(json.dumps(scan(), indent=2, default=str))


def cmd_selftest(args: argparse.Namespace) -> None:
    """Run the backend test suite and record the outcome for the Overview pipeline timeline."""
    import subprocess
    from datetime import datetime, timezone

    from lifecycle.config import processed_dir

    res = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider"], cwd=REPO_ROOT / "backend",
                         capture_output=True, text=True)
    lines = [ln for ln in res.stdout.strip().splitlines() if " passed" in ln or " failed" in ln]
    tail = lines[-1] if lines else (res.stdout.strip().splitlines() or [""])[-1]
    import re

    passed = int(re.search(r"(\d+) passed", tail).group(1)) if re.search(r"(\d+) passed", tail) else 0
    failed = int(re.search(r"(\d+) failed", tail).group(1)) if re.search(r"(\d+) failed", tail) else 0
    rep = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "passed": passed, "failed": failed,
           "summary": tail, "returncode": res.returncode}
    (processed_dir() / "test_report.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    sys.exit(res.returncode)


def cmd_openapi(args: argparse.Namespace) -> None:
    from lifecycle.api.main import app

    Path(args.out).write_text(json.dumps(app.openapi(), indent=2))
    print("wrote", args.out)


def main() -> None:
    ap = argparse.ArgumentParser(prog="lifecycle")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("--wrds", action="store_true", help="also pull WRDS (needs WRDS_USERNAME / Duo approval)")
    p.add_argument("--offline", action="store_true", help="use the committed public snapshot instead of downloading")
    p.set_defaults(fn=cmd_ingest)
    sub.add_parser("snapshot", help="refresh snapshots/public from the live sources").set_defaults(fn=cmd_snapshot)
    sub.add_parser("build-panel").set_defaults(fn=cmd_build)
    p = sub.add_parser("seed")
    p.add_argument("--full", action="store_true")
    p.set_defaults(fn=cmd_seed)
    p = sub.add_parser("spec")
    p.add_argument("paths", nargs="+")
    p.set_defaults(fn=cmd_spec)
    p = sub.add_parser("reproduce")
    p.add_argument("run_id")
    p.set_defaults(fn=cmd_reproduce)
    p = sub.add_parser("seed-v2", help="run the default v2 studies (F1-F6)")
    p.add_argument("--only", nargs="*", default=None)
    p.add_argument("--pp-universe", default=None, help="universe for the Permanent Portfolio study")
    p.add_argument("--force", action="store_true", help="re-execute even when a cached run exists")
    p.set_defaults(fn=cmd_seed_v2)
    sub.add_parser("market-refresh", help="download US Treasury daily par curves").set_defaults(fn=cmd_market_refresh)
    sub.add_parser("entitlements", help="read-only WRDS entitlement/schema scan").set_defaults(fn=cmd_entitlements)
    sub.add_parser("selftest", help="run pytest and record the result").set_defaults(fn=cmd_selftest)
    p = sub.add_parser("openapi")
    p.add_argument("out")
    p.set_defaults(fn=cmd_openapi)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
