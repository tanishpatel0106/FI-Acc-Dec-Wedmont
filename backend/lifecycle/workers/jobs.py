"""Job entry point shared by the in-process executor and arq workers."""
from lifecycle.runs.executor import execute


def run_job(run_id: str) -> None:
    execute(run_id)
