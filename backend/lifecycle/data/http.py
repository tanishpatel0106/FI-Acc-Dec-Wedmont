"""Download helper that keeps a dated raw copy of every public file (idempotent per day).

Short connect/read timeouts with retries, and a progress line per file, so a slow or blocked
host is visible and skipped quickly instead of looking like a hang. Files already downloaded
today are reused, so an interrupted `make data` resumes where it stopped.
"""
import time
from datetime import date
from pathlib import Path

import httpx

from lifecycle.config import raw_dir

TIMEOUT = httpx.Timeout(45.0, connect=10.0)
RETRIES = 3


def fetch(url: str, name: str, refresh: bool = False) -> Path:
    folder = raw_dir() / "public" / date.today().isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    if target.exists() and not refresh and target.stat().st_size > 0:
        print("  cached   " + name, flush=True)
        return target
    headers = {"User-Agent": "Mozilla/5.0 (LIFECYCLE research platform; academic use)"}
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        t0 = time.time()
        try:
            with httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
            if resp.status_code != 200:
                raise RuntimeError("HTTP " + str(resp.status_code))
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(resp.content)
            tmp.replace(target)  # never leave a truncated file that would be reused as cached
            print("  fetched  %-28s %7.1f KB  %5.1fs" % (name, len(resp.content) / 1024, time.time() - t0), flush=True)
            return target
        except Exception as exc:  # timeouts, connection errors, non-200
            last_error = exc
            print("  retry %d/%d %s: %s (%.0fs)" % (attempt, RETRIES, name, exc, time.time() - t0), flush=True)
            if attempt < RETRIES:
                time.sleep(2 ** attempt)
    raise RuntimeError("download failed after %d attempts: %s (%s)" % (RETRIES, url, last_error))


def complete_months(daily_index) -> "object":
    """Month-ends whose month is fully observed (drops the current, partial month of a daily series)."""
    import pandas as pd

    last = pd.Timestamp(daily_index.max()).normalize()
    # complete only if the last observation reaches the month's last business day
    if last >= last + pd.offsets.BMonthEnd(0):
        return last + pd.offsets.MonthEnd(0)
    return last - pd.offsets.MonthEnd(1)
