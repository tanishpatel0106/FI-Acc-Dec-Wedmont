"""Committed snapshot of the public sources, so `make data-offline` needs no network.

The snapshot holds the per-source frames exactly as the ingestion scripts produce them
(canonical panel rows with source, provenance and vintage), plus the life table and a
manifest with row counts, coverage and SHA-256 hashes. WRDS data is never snapshotted.
"""
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from lifecycle.config import REPO_ROOT, processed_dir, raw_dir

SNAPSHOT_DIR = REPO_ROOT / "snapshots" / "public"
SOURCES = {
    "french": "https://mba.tuck.dartmouth.edu/pages/faculty/Ken.French/data_library.html",
    "fred": "https://fred.stlouisfed.org/ (fredgraph CSV or FRED API)",
    "gsw": "https://www.federalreserve.gov/data/nominal-yield-curve.htm (feds200628, feds200805)",
    "acm": "https://www.newyorkfed.org/research/data_indicators/term-premia-tabs",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_snapshot(dest: Path = SNAPSHOT_DIR) -> dict:
    """Pull every public source now and write the snapshot (used to refresh the committed copy)."""
    from lifecycle.data import ingest_acm, ingest_fred, ingest_french, ingest_gsw, ingest_ssa

    dest.mkdir(parents=True, exist_ok=True)
    pulls = {"french": ingest_french.pull_french, "fred": ingest_fred.pull_fred, "gsw": ingest_gsw.pull_gsw,
             "acm": ingest_acm.pull_acm}
    manifest: dict = {"vintage": date.today().isoformat(), "created_at": pd.Timestamp.now().isoformat(),
                      "files": {}, "note": "public sources only; WRDS data is never committed"}
    for name, fn in pulls.items():
        frame = fn()
        path = dest / (name + ".parquet")
        frame.to_parquet(path, index=False)
        manifest["files"][name] = {
            "rows": int(len(frame)), "series": sorted(frame["series_id"].unique().tolist()),
            "first_month": str(pd.to_datetime(frame["month_end"]).min().date()),
            "last_month": str(pd.to_datetime(frame["month_end"]).max().date()),
            "source": SOURCES[name], "sha256": _sha256(path)}
        print("snapshot", name, len(frame), "rows")
    life = ingest_ssa.pull_ssa()
    life_path = dest / "life_table.parquet"
    life.to_parquet(life_path, index=False)
    manifest["files"]["life_table"] = {"rows": int(len(life)), "source": str(life["source"].iloc[0]),
                                       "provenance": str(life["provenance"].iloc[0]), "sha256": _sha256(life_path)}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def load_snapshot(src: Path = SNAPSHOT_DIR) -> dict:
    """Install the committed snapshot into data/raw (under its original vintage) and the life table."""
    manifest_path = src / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("no public snapshot at " + str(src))
    manifest = json.loads(manifest_path.read_text())
    vintage = manifest["vintage"]
    for name, info in manifest["files"].items():
        path = src / (name + ".parquet")
        if _sha256(path) != info["sha256"]:
            raise RuntimeError("snapshot file changed since the manifest was written: " + path.name)
        if name == "life_table":
            shutil.copyfile(path, processed_dir() / "life_table.parquet")
            continue
        folder = raw_dir() / ("public_" + name) / vintage
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, folder / (name + ".parquet"))
        print("ok   %-7s %7d rows  (snapshot %s, %s -> %s)" % (name, info["rows"], vintage, info["first_month"],
                                                              info["last_month"]))
    return manifest
