"""Server-side, read-only WRDS entitlement and schema discovery (brief 4.3), plus the source-rights registry.

`scan()` connects once (one Duo approval), lists the candidate libraries and tables, runs a 5-row sample
query per desired source, and records first/last dates and null rates. The result is written to
data/catalog/entitlements.json (server-local; usernames, hosts and tokens are never stored). The API only
exposes the status labels, never table contents.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from lifecycle.config import data_dir

STATUSES = ("AVAILABLE", "AVAILABLE_WITH_RESTRICTED_TERMS", "PARTIAL", "UNAVAILABLE_PERMISSION", "UNAVAILABLE_SCHEMA",
            "UNAVAILABLE_COVERAGE", "ERROR_RETRYABLE", "NOT_SCANNED")

# canonical source -> (library, candidate tables, date column, key columns)
TARGETS = {
    "crsp_index (us_eq)": ("crsp", ["msi", "msix", "inddlymthseriesdata_ind"], "date", ["vwretd"]),
    "crsp_treasury_monthly (ust_*)": ("crsp", ["mcti", "tfz_mth_ft", "tfz_mth_rf"], "caldt", []),
    "crsp_etf_msf (GLD/TLT/TIP/IEF/LQD)": ("crsp", ["msf_v2", "msf"], "date", ["ret"]),
    "crsp_names (PERMNO spells)": ("crsp", ["stksecurityinfohist", "msenames"], None, []),
    "wrds_bond_returns (IG/HY)": ("wrdsapps_bondret", ["bondret"], "date", ["ret_eom"]),
    "fisd (bond reference)": ("fisd", ["fisd_mergedissue", "mergedissue"], None, []),
    "trace (bond trades)": ("trace", ["trace_enhanced", "trace"], None, []),
}

SOURCE_RIGHTS = [
    {"source": "fred", "licence_class": "public_with_terms", "redistribution": "derived statistics; check per-series "
     "notes (ICE BofA OAS: restricted 3-year history)", "terms": "https://fred.stlouisfed.org/legal/"},
    {"source": "french", "licence_class": "public_with_terms", "redistribution": "derived statistics with citation",
     "terms": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"},
    {"source": "fed", "licence_class": "public_open", "redistribution": "public domain (US government)",
     "terms": "https://www.federalreserve.gov/data/nominal-yield-curve.htm"},
    {"source": "nyfed", "licence_class": "public_open", "redistribution": "public with attribution",
     "terms": "https://www.newyorkfed.org/research/data_indicators/term-premia-tabs"},
    {"source": "treasury_daily", "licence_class": "public_open", "redistribution": "public domain (US Treasury)",
     "terms": "https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics"},
    {"source": "ssa", "licence_class": "public_open", "redistribution": "public domain (SSA)",
     "terms": "https://www.ssa.gov/oact/STATS/table4c6.html"},
    {"source": "wrds", "licence_class": "wrds_restricted", "redistribution": "NEVER raw rows; aggregate derived "
     "results only, subject to the institution's WRDS agreement", "terms": "institutional WRDS subscription"},
    {"source": "world_gold_council", "licence_class": "public_with_terms", "redistribution": "NOT ingested: LBMA "
     "benchmark history is licence-restricted; requires human rights review", "terms": "https://www.gold.org/goldhub/data/gold-prices"},
    {"source": "model", "licence_class": "derived", "redistribution": "derived from public yields (follows the input "
     "series' terms)", "terms": "n/a"},
]


def path():
    p = data_dir() / "catalog"
    p.mkdir(parents=True, exist_ok=True)
    return p / "entitlements.json"


def load() -> dict[str, Any]:
    p = path()
    if not p.exists():
        return {"scanned_at": None, "attempt_id": None,
                "targets": {k: {"status": "NOT_SCANNED", "library": v[0]} for k, v in TARGETS.items()},
                "note": "run `python -m lifecycle.cli entitlements` on the authorised research host"}
    return json.loads(p.read_text())


def _classify(exc: Exception) -> str:
    msg = str(exc).lower()
    if "permission" in msg or "denied" in msg or "not authorized" in msg:
        return "UNAVAILABLE_PERMISSION"
    if "does not exist" in msg or "undefined" in msg or "relation" in msg:
        return "UNAVAILABLE_SCHEMA"
    if "timeout" in msg or "connection" in msg or "duo" in msg:
        return "ERROR_RETRYABLE"
    return "ERROR_RETRYABLE"


def scan() -> dict[str, Any]:
    from lifecycle.data import wrds_client

    attempt = uuid.uuid4().hex[:12]
    out: dict[str, Any] = {"scanned_at": datetime.now(timezone.utc).isoformat(), "attempt_id": attempt, "targets": {}}
    t0 = time.time()
    db = wrds_client.connect()
    try:
        libs = set(db.list_libraries())
        for name, (lib, tables, date_col, cols) in TARGETS.items():
            rec: dict[str, Any] = {"library": lib}
            if lib not in libs:
                rec["status"] = "UNAVAILABLE_PERMISSION"
                rec["detail"] = "library not listed for this account"
                out["targets"][name] = rec
                continue
            try:
                avail = set(db.list_tables(library=lib))
            except Exception as exc:
                rec.update({"status": _classify(exc), "detail": str(exc)[:200]})
                out["targets"][name] = rec
                continue
            found = [t for t in tables if t in avail]
            if not found:
                rec.update({"status": "UNAVAILABLE_SCHEMA", "detail": "none of %s present" % tables})
                out["targets"][name] = rec
                continue
            t = found[0]
            rec["table"] = t
            try:
                sample = db.raw_sql("select * from %s.%s limit 5" % (lib, t))
                rec["columns"] = list(sample.columns)[:40]
                rec["missing_expected_columns"] = [c for c in cols if c not in sample.columns]
                if date_col and date_col in sample.columns:
                    rng = db.raw_sql("select min(%s) as lo, max(%s) as hi, count(*) as n from %s.%s" % (
                        date_col, date_col, lib, t))
                    rec.update({"first": str(rng["lo"].iloc[0]), "last": str(rng["hi"].iloc[0]),
                                "row_estimate": int(rng["n"].iloc[0])})
                rec["null_rate_sample"] = {c: float(sample[c].isna().mean()) for c in cols if c in sample.columns}
                rec["status"] = "PARTIAL" if rec["missing_expected_columns"] else "AVAILABLE_WITH_RESTRICTED_TERMS"
            except Exception as exc:
                rec.update({"status": _classify(exc), "detail": str(exc)[:200]})
            out["targets"][name] = rec
    finally:
        wrds_client.close_all()
    out["seconds"] = time.time() - t0
    out["note"] = "server-local; contains no credentials, hosts or raw rows"
    path().write_text(json.dumps(out, indent=2))
    return out


def public_view() -> dict[str, Any]:
    """Entitlement labels only (what the browser may see)."""
    e = load()
    return {"scanned_at": e.get("scanned_at"), "attempt_id": e.get("attempt_id"),
            "targets": {k: {"status": v.get("status"), "library": v.get("library"), "first": v.get("first"),
                            "last": v.get("last")} for k, v in e.get("targets", {}).items()},
            "rights": SOURCE_RIGHTS, "note": e.get("note")}
