"""
backend/app/models/job.py
----------------------------
Purpose: Defines the Job table -- tracks the status of a long-running
background task (OCR + AI extraction), so the frontend can poll
"is it done yet?" without the HTTP request itself waiting 20-60 seconds.

Why this file exists: File uploads trigger a Celery background task
(built in Phase 3). This table is the shared status board between the
upload endpoint (creates the Job), the Celery worker (updates it), and
the frontend (polls it via GET /jobs/{id}).
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Enum, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class JobType(str, enum.Enum):
    """
    Purpose: Distinguishes which kind of background task this job is,
    so the worker (Phase 3) knows which processing function to run.
    """
    TENDER_EXTRACTION = "TENDER_EXTRACTION"
    BIDDER_EXTRACTION = "BIDDER_EXTRACTION"


class JobStatus(str, enum.Enum):
    """
    Purpose: The lifecycle of a background task, from creation to finish.
    Where it's used: Job.status column below. GET /jobs/{id} returns this
    directly to the frontend's polling component.
    """
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class Job(Base):
    """
    Purpose: One row per background processing task. Created immediately
    when a file is uploaded (status=PENDING), updated by the Celery
    worker as it processes (RUNNING -> DONE or FAILED).

    Where it's used: Created in routers/tenders.py and routers/bidders.py
    (Phase 2) right after a file upload, before Celery exists yet. Updated
    by workers/tasks.py (Phase 3). Read by routers/jobs.py's polling endpoint.
    """
    __tablename__ = "jobs"

    # UUID string instead of an auto-increment integer, so job IDs are
    # unguessable and can be safely returned to the frontend immediately.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)

    tender_id: Mapped[int | None] = mapped_column(ForeignKey("tenders.id"), nullable=True)

    bidder_id: Mapped[int | None] = mapped_column(ForeignKey("bidders.id"), nullable=True)

    type: Mapped[JobType] = mapped_column(Enum(JobType), nullable=False)

    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)