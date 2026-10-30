"""SQLite run registry + on-disk result store (data/runs/<run_id>/)."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lifecycle.config import runs_dir

_LOCK = threading.Lock()

SCHEMA = """
create table if not exists runs (
    run_id text primary key,
    kind text not null,
    status text not null,
    stage text not null,
    progress real not null default 0,
    label text,
    parent_id text,
    spec_json text not null,
    spec_hash text not null,
    catalog_hash text,
    engine_version text,
    lock_hash text,
    created_at text not null,
    started_at text,
    finished_at text,
    timings_json text,
    warnings_json text,
    error text,
    summary_json text
);
create index if not exists runs_kind on runs(kind, created_at);
create index if not exists runs_parent on runs(parent_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _db_path() -> Path:
    return runs_dir() / "registry.sqlite"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(), timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def create(run_id: str, kind: str, spec_json: str, spec_hash: str, catalog_hash: str | None, engine_version: str,
           lock_hash: str, label: str | None = None, parent_id: str | None = None) -> None:
    with _LOCK, _conn() as con:
        con.execute("insert or ignore into runs (run_id, kind, status, stage, progress, label, parent_id, spec_json,"
                    " spec_hash, catalog_hash, engine_version, lock_hash, created_at) values"
                    " (?, ?, 'queued', 'queued', 0, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (run_id, kind, label, parent_id, spec_json, spec_hash, catalog_hash, engine_version, lock_hash,
                     now()))


def get(run_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute("select * from runs where run_id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    out = dict(row)
    for k in ["timings_json", "warnings_json", "summary_json", "spec_json"]:
        if out.get(k):
            out[k[:-5]] = json.loads(out[k])
        else:
            out[k[:-5]] = None
        out.pop(k, None)
    return out


def update(run_id: str, **fields: Any) -> None:
    if len(fields) == 0:
        return
    cols = []
    vals = []
    for k, v in fields.items():
        if k in ("timings", "warnings", "summary"):
            from lifecycle.runs.jsonsafe import clean

            k = k + "_json"
            v = json.dumps(clean(v), default=str)
        cols.append(k + " = ?")
        vals.append(v)
    vals.append(run_id)
    with _LOCK, _conn() as con:
        con.execute("update runs set " + ", ".join(cols) + " where run_id = ?", vals)


def reset(run_id: str) -> None:
    update(run_id, status="queued", stage="queued", progress=0.0, error=None, started_at=None, finished_at=None)


def list_runs(kind: str | None = None, limit: int = 100, parent_id: str | None = None,
              include_children: bool = False) -> list[dict[str, Any]]:
    q = ("select run_id, kind, status, stage, progress, label, parent_id, spec_hash, catalog_hash, engine_version,"
         " created_at, finished_at, summary_json, error from runs where 1=1")
    args: list[Any] = []
    if kind is not None:
        q += " and kind = ?"
        args.append(kind)
    if parent_id is not None:
        q += " and parent_id = ?"
        args.append(parent_id)
    elif not include_children:
        q += " and parent_id is null"
    q += " order by created_at desc limit ?"
    args.append(limit)
    with _conn() as con:
        rows = con.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["summary"] = json.loads(d.pop("summary_json")) if d.get("summary_json") else None
        out.append(d)
    return out


def run_folder(run_id: str) -> Path:
    path = runs_dir() / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_results(run_id: str, results: dict[str, Any]) -> None:
    from lifecycle.runs.jsonsafe import clean

    (run_folder(run_id) / "results.json").write_text(json.dumps(clean(results), default=_json_default))


def load_results(run_id: str) -> dict[str, Any] | None:
    path = runs_dir() / run_id / "results.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _json_default(o: Any) -> Any:
    import numpy as np

    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)
