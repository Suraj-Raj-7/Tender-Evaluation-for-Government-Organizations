"""
backend/app/routers/jobs.py
------------------------------
Purpose: Lets the frontend poll a background job's status. The jobs
themselves aren't created by real processing yet (that's Phase 2/3) --
this endpoint just reads whatever Job rows exist.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.job import Job
from app.schemas.job import JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns one job's current status. Frontend's JobStatusPoller (Phase 5)
    calls this every 3 seconds while status is PENDING or RUNNING."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job