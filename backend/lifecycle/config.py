"""Paths, environment loading and engine version."""
import os
import subprocess
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]

# .env lives at the repository root; never committed
load_dotenv(REPO_ROOT / ".env", override=False)


def data_dir() -> Path:
    raw = os.environ.get("LIFECYCLE_DATA_DIR", "")
    if raw == "":
        path = REPO_ROOT / "data"
    else:
        path = Path(raw)
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def raw_dir() -> Path:
    path = data_dir() / "raw"
    path.mkdir(parents=True, exist_ok=True)
    return path


def processed_dir() -> Path:
    path = data_dir() / "processed"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def runs_dir() -> Path:
    path = data_dir() / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


@lru_cache(maxsize=1)
def engine_version() -> str:
    """Package version plus git SHA when available."""
    from lifecycle import __version__

    sha = os.environ.get("LIFECYCLE_GIT_SHA", "")
    if sha == "":
        try:
            out = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=REPO_ROOT,
                                 capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                sha = out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            sha = ""
    if sha == "":
        sha = "nogit"
    return __version__ + "+" + sha


def lockfile_hash() -> str:
    import hashlib

    lock = REPO_ROOT / "backend" / "uv.lock"
    if not lock.exists():
        return "nolock"
    return hashlib.sha256(lock.read_bytes()).hexdigest()[:16]
