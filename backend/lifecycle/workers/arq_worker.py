"""arq worker on Redis (optional; set REDIS_URL). Start with: arq lifecycle.workers.arq_worker.WorkerSettings"""
import asyncio
import os
from typing import Any

from lifecycle.workers.jobs import run_job


async def execute_run(ctx: dict[str, Any], run_id: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, run_job, run_id)


def _settings() -> Any:
    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379"))


class WorkerSettings:
    functions = [execute_run]
    max_jobs = 1
    job_timeout = 6 * 3600

    @staticmethod
    def redis_settings() -> Any:  # pragma: no cover - evaluated by arq
        return _settings()


def enqueue(run_id: str) -> None:
    from arq import create_pool

    async def _go() -> None:
        pool = await create_pool(_settings())
        await pool.enqueue_job("execute_run", run_id)
        await pool.close()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        loop.create_task(_go())
    else:
        asyncio.run(_go())


WorkerSettings.redis_settings = _settings()  # type: ignore[assignment]
