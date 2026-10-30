"""WRDS connection helpers with runtime schema lookup (CRSP SIZ -> CIZ migration safe).

Credentials come from WRDS_USERNAME / WRDS_PASSWORD (repo-root .env) or ~/.pgpass.
The first connection triggers a Duo push that must be approved on the phone.
"""
import os

import pandas as pd

from lifecycle import config  # noqa: F401  (loads .env)

_SHARED = {"db": None}


def connect():
    """One shared connection per process so a full ingest needs a single Duo approval."""
    if _SHARED["db"] is not None:
        return _SHARED["db"]
    try:
        import wrds
    except ImportError as exc:
        raise RuntimeError("the 'wrds' package is not installed: uv pip install -e '.[wrds]'") from exc
    username = os.environ.get("WRDS_USERNAME", "")
    if username == "":
        raise RuntimeError("WRDS_USERNAME is not set (add it to the repository .env)")
    password = os.environ.get("WRDS_PASSWORD", "")
    print("connecting to WRDS as", username, "- approve the Duo push on your phone")
    if password != "":
        # passed straight to the client (and libpq as a fallback) so there is no interactive prompt
        os.environ["PGPASSWORD"] = password
        _SHARED["db"] = wrds.Connection(wrds_username=username, wrds_password=password)
    else:
        _SHARED["db"] = wrds.Connection(wrds_username=username)  # falls back to ~/.pgpass or a prompt
    return _SHARED["db"]


def release(db) -> None:
    """Keep the shared connection open; close_all() ends it."""
    if db is not _SHARED["db"]:
        db.close()


def close_all() -> None:
    if _SHARED["db"] is not None:
        _SHARED["db"].close()
        _SHARED["db"] = None


def table_exists(db, library: str, table: str) -> bool:
    try:
        tables = db.list_tables(library=library)
    except Exception:
        return False
    return table in tables


def resolve_table(db, candidates: list[tuple[str, str]]) -> tuple[str, str]:
    """Return the first (library, table) that exists in this subscription."""
    for i in range(len(candidates)):
        library, table = candidates[i]
        if table_exists(db, library, table):
            return library, table
    raise RuntimeError("none of the candidate WRDS tables exist: " + str(candidates))


def columns_of(db, library: str, table: str) -> list[str]:
    described = db.describe_table(library=library, table=table)
    return [str(x).lower() for x in list(described["name"])]


def pick_column(available: list[str], candidates: list[str]) -> str | None:
    for i in range(len(candidates)):
        if candidates[i] in available:
            return candidates[i]
    return None


def to_month_end(values) -> pd.Series:
    return pd.to_datetime(values) + pd.offsets.MonthEnd(0)
