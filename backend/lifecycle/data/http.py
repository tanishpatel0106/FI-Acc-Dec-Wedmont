"""Download helper that keeps a dated raw copy of every public file (idempotent per day)."""
from datetime import date
from pathlib import Path

import httpx

from lifecycle.config import raw_dir


def fetch(url: str, name: str, refresh: bool = False, timeout: float = 120.0) -> Path:
    folder = raw_dir() / "public" / date.today().isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    if target.exists() and not refresh and target.stat().st_size > 0:
        return target
    headers = {"User-Agent": "Mozilla/5.0 (LIFECYCLE research platform; academic use)"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        if resp.status_code != 200:
            raise RuntimeError("download failed (" + str(resp.status_code) + "): " + url)
        target.write_bytes(resp.content)
    return target
