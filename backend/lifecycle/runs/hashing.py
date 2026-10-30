"""Canonical JSON and content hashes."""
import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_json(obj: Any) -> str:
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="json")
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def spec_hash(obj: Any) -> str:
    return sha256_hex(canonical_json(obj))


def run_id_for(kind: str, obj: Any) -> str:
    """Run ID = SHA-256 of kind + canonical spec (first 20 hex chars keep URLs short)."""
    return sha256_hex(kind + ":" + canonical_json(obj))[:20]
