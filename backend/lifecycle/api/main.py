"""FastAPI service (OpenAPI v1). All analytics are computed server-side and addressed by run ID."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from lifecycle import __version__
from lifecycle.api.common import Problem, generic_handler, problem_handler
from lifecycle.api.routers import experiments, market, research, v2
from lifecycle.config import engine_version

app = FastAPI(title="LIFECYCLE API", version=__version__,
              description="Multi-asset portfolio optimisation & lifetime utility research platform. "
                          "Research output only - not investment advice.")
origins = [o.strip() for o in os.environ.get("API_CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins + ["http://127.0.0.1:3000"], allow_methods=["*"],
                   allow_headers=["*"], expose_headers=["X-Run-Id", "X-Spec-Hash", "X-Catalog-Hash",
                                                        "Content-Disposition"])
app.add_middleware(GZipMiddleware, minimum_size=2048)
app.add_exception_handler(Problem, problem_handler)  # type: ignore[arg-type]
# typed handlers run inside the CORS middleware, so browsers can read the RFC 9457 error body
for _exc in (ValueError, KeyError, FileNotFoundError, RuntimeError, IndexError, TypeError):
    app.add_exception_handler(_exc, generic_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, generic_handler)
app.include_router(market.router)
app.include_router(experiments.router)
app.include_router(research.router)
app.include_router(v2.router)


@app.get("/health")
def health() -> dict:
    from lifecycle import ENGINE_SEMANTIC_VERSION

    try:
        from lifecycle.data import panel

        data = {"catalog_hash": panel.catalog_hash(), "as_of": panel.as_of()}
    except Exception as exc:  # report data availability honestly without leaking paths or credentials
        data = {"error": type(exc).__name__}
    return {"status": "ok", "engine_version": engine_version(), "semantic_version": ENGINE_SEMANTIC_VERSION,
            "data": data, "redis": bool(os.environ.get("REDIS_URL"))}
