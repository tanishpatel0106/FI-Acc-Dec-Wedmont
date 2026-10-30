"""Command line: ingestion, seeding default exhibits, sweeps, reproduction and OpenAPI export.

    python -m lifecycle.cli ingest [--wrds]
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

    run_all(include_wrds=args.wrds)


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


def cmd_openapi(args: argparse.Namespace) -> None:
    from lifecycle.api.main import app

    Path(args.out).write_text(json.dumps(app.openapi(), indent=2))
    print("wrote", args.out)


def main() -> None:
    ap = argparse.ArgumentParser(prog="lifecycle")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("--wrds", action="store_true", help="also pull WRDS (needs WRDS_USERNAME / Duo approval)")
    p.set_defaults(fn=cmd_ingest)
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
    p = sub.add_parser("openapi")
    p.add_argument("out")
    p.set_defaults(fn=cmd_openapi)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
