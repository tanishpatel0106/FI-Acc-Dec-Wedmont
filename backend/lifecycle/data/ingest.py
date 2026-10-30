"""Ingestion orchestrators: public sources (no credentials) and WRDS (Duo push)."""
import traceback

from lifecycle.data.normalize import build_panel, write_raw


def run_public() -> None:
    from lifecycle.data import ingest_acm, ingest_fred, ingest_french, ingest_gsw, ingest_ssa

    steps = [("french", "french", ingest_french.pull_french), ("fred", "fred", ingest_fred.pull_fred),
             ("gsw", "gsw", ingest_gsw.pull_gsw), ("acm", "acm", ingest_acm.pull_acm)]
    for group, name, fn in steps:
        try:
            frame = fn()
            path = write_raw(frame, "public_" + group, name)
            print("ok", name, len(frame), "rows ->", path)
        except Exception as exc:
            print("FAILED", name, exc)
            traceback.print_exc()
    ingest_ssa.pull_ssa()


def run_wrds() -> None:
    from lifecycle.data import (
        ingest_bondret,
        ingest_crsp_index,
        ingest_crsp_mcti,
        ingest_crsp_tfz,
        ingest_etfs,
        ingest_ff,
    )

    steps = [("crsp_index", ingest_crsp_index.pull_crsp_index), ("crsp_mcti", ingest_crsp_mcti.pull_mcti),
             ("crsp_tfz", ingest_crsp_tfz.pull_tfz), ("ff", ingest_ff.pull_ff),
             ("bondret", ingest_bondret.pull_bondret), ("etfs", ingest_etfs.pull_etfs)]
    from lifecycle.data import wrds_client

    try:
        for name, fn in steps:
            try:
                frame = fn()
                path = write_raw(frame, "wrds", name)
                print("ok", name, len(frame), "rows ->", path)
            except Exception as exc:
                print("FAILED", name, exc)
    finally:
        wrds_client.close_all()


def run_all(include_wrds: bool) -> dict:
    run_public()
    if include_wrds:
        run_wrds()
    meta = build_panel()
    print("panel built: catalog_hash", meta["catalog_hash"], "series", meta["n_series"])
    return meta
