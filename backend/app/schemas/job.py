"""
backend/app/schemas/job.py
------------------------------
Purpose: JSON shape for background job status, polled by the frontend.
"""

from datetime import datetime
from pydantic import BaseModel
from app.models.job import JobType, JobStatus


class JobResponse(BaseModel):
    """
    Job status data. Used by: GET /jobs/{id}, polled every 3 seconds
    by the frontend.

    result_summary is only populated once status is DONE -- it holds
    {"criteria_count": N} for a TENDER_EXTRACTION job, or
    {"evidence_count": N} for a BIDDER_EXTRACTION job, so the frontend
    can show "18 criteria found" without a separate API call.
    """
    id: str
    type: JobType
    status: JobStatus
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    result_summary: dict | None = None

    model_config = {"from_attributes": True}