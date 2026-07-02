"""
backend/app/schemas/job.py
------------------------------
Purpose: JSON shape for background job status, polled by the frontend.
"""

from datetime import datetime
from pydantic import BaseModel
from app.models.job import JobType, JobStatus


class JobResponse(BaseModel):
    """Job status data. Used by: GET /jobs/{id}, polled every 3 seconds by the frontend."""
    id: str
    type: JobType
    status: JobStatus
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}