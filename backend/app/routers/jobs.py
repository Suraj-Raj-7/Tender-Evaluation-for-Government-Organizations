"""
backend/app/routers/jobs.py
------------------------------
Purpose: Lets the frontend poll a background job's status, including a
short summary of what the job produced once it's finished.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.job import Job, JobType, JobStatus
from app.models.criterion import Criterion
from app.models.evidence import Evidence
from app.schemas.job import JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _build_result_summary(job: Job, db: Session) -> dict | None:
    """
    Purpose: Builds the {"criteria_count": N} or {"evidence_count": N}
    summary for a finished job, by actually counting the real rows it
    produced -- not guessing or caching a number.

    Where it gets its data: job is the Job row already queried by
    get_job_status() below. db is that same request's session.

    Where it's used: Called once by get_job_status(), only when the
    job's status is DONE.
    """
    if job.status != JobStatus.DONE:
        return None

    if job.type == JobType.TENDER_EXTRACTION:
        count = db.query(Criterion).filter(Criterion.tender_id == job.tender_id).count()
        return {"criteria_count": count}

    if job.type == JobType.BIDDER_EXTRACTION:
        count = db.query(Evidence).filter(Evidence.bidder_id == job.bidder_id).count()
        return {"evidence_count": count}

    return None


@router.get("/{job_id}", response_model=JobResponse)
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns one job's current status, plus a result summary once DONE.
    Frontend's JobStatusPoller (Phase 5) calls this every 3 seconds while
    status is PENDING or RUNNING."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return JobResponse(
        id=job.id,
        type=job.type,
        status=job.status,
        error_message=job.error_message,
        started_at=job.started_at,
        finished_at=job.finished_at,
        result_summary=_build_result_summary(job, db),
    )