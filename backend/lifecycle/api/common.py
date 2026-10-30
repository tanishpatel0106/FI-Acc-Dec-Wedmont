"""Response envelope (run_id, spec_hash, catalog_hash, engine_version, generated_at) and RFC 9457 errors."""
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from lifecycle.config import engine_version
from lifecycle.data import panel
from lifecycle.runs import registry
from lifecycle.runs.jsonsafe import clean


def catalog_hash_or_none() -> str | None:
    try:
        return panel.catalog_hash()
    except Exception:
        return None


def envelope(payload: dict[str, Any], run_id: str | None = None, spec_hash: str | None = None,
             catalog_hash: str | None = None) -> dict[str, Any]:
    out = {"run_id": run_id, "spec_hash": spec_hash, "catalog_hash": catalog_hash or catalog_hash_or_none(),
           "engine_version": engine_version(), "generated_at": registry.now()}
    out.update(payload)
    return clean(out)


class Problem(Exception):
    def __init__(self, status: int, title: str, detail: str = "", type_: str = "about:blank") -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type = type_


async def problem_handler(request: Request, exc: Problem) -> JSONResponse:
    return JSONResponse(status_code=exc.status, media_type="application/problem+json",
                        content={"type": exc.type, "title": exc.title, "status": exc.status, "detail": exc.detail,
                                 "instance": str(request.url.path)})


async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
    status = 500
    title = "Internal error"
    if isinstance(exc, FileNotFoundError):
        status, title = 503, "Data not available"
    elif isinstance(exc, (KeyError, ValueError)):
        status, title = 400, "Bad request"
    return JSONResponse(status_code=status, media_type="application/problem+json",
                        content={"type": "about:blank", "title": title, "status": status, "detail": str(exc),
                                 "instance": str(request.url.path)})


def run_row_or_404(run_id: str) -> dict[str, Any]:
    row = registry.get(run_id)
    if row is None:
        raise Problem(404, "Run not found", "no run with id " + run_id)
    return row
