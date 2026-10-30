"""Ingestion orchestrators: public sources (no credentials) and WRDS (Duo push)."""
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from lifecycle.data.normalize import build_panel, write_raw


def run_public() -> None:
    """Pull every public source concurrently; a failing source is reported and the rest continue."""
    from lifecycle.data import ingest_acm, ingest_fred, ingest_french, ingest_gsw, ingest_ssa

    steps = [("french", ingest_french.pull_french), ("fred", ingest_fred.pull_fred),
             ("gsw", ingest_gsw.pull_gsw), ("acm", ingest_acm.pull_acm)]

    def one(name, fn):
        t0 = time.time()
        frame = fn()
        path = write_raw(frame, "public_" + name, name)
        return "ok   %-7s %7d rows  %5.1fs  -> %s" % (name, len(frame), time.time() - t0, path)

    print("downloading public sources (French library, FRED, Fed GSW curves, NY Fed ACM, SSA)...", flush=True)
    with ThreadPoolExecutor(max_workers=len(steps) + 1) as pool:
        futures = {pool.submit(one, name, fn): name for name, fn in steps}
        futures[pool.submit(ingest_ssa.pull_ssa)] = "ssa"
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                msg = fut.result()
                if name == "ssa":
                    msg = "ok   ssa     life table"
                print(msg, flush=True)
            except Exception as exc:
                print("FAILED", name, exc, flush=True)
                traceback.print_exc()


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


def run_all(include_wrds: bool, offline: bool = False) -> dict:
    if offline:
        from lifecycle.data.snapshot import load_snapshot

        print("loading the committed public-data snapshot (no network)...", flush=True)
        load_snapshot()
    else:
        run_public()
    if include_wrds:
        run_wrds()
    meta = build_panel()
    print("panel built: catalog_hash", meta["catalog_hash"], "series", meta["n_series"])
    return meta
