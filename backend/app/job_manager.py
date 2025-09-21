# backend/app/job_manager.py
import uuid
from typing import Any, Dict

"""
Simple in-memory job manager for demo/hackathon use.

Warning: ephemeral (lost on restart). Swap to Redis/Celery for production.
"""
JOBS: Dict[str, Dict[str, Any]] = {}

def create_job() -> str:
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "pending", "result": None, "error": None}
    return job_id

def set_job_running(job_id: str):
    if job_id in JOBS:
        JOBS[job_id]["status"] = "running"

def set_job_done(job_id: str, result: Any):
    if job_id in JOBS:
        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["result"] = result

def set_job_failed(job_id: str, err: str):
    if job_id in JOBS:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = err

def get_job(job_id: str):
    return JOBS.get(job_id)
