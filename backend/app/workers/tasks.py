"""
backend/app/workers/tasks.py
--------------------------------
Purpose: The actual Celery task functions -- the code that runs in the
background worker process, not in the FastAPI request/response cycle.
This is where OCR (Phase 2), AI extraction (this phase's parser
files), and the database finally get tied together into one pipeline.

Why this file exists: Routers only ever CREATE a Job row and call
.delay() on a task here -- they never run OCR/AI themselves, since
that would block the HTTP response for 20-60 seconds. This file is
where that slow work actually happens, safely isolated in its own
process.

IMPORTANT: Celery tasks run in a separate process from FastAPI, so
they cannot reuse FastAPI's per-request get_db() session. Each task
opens and closes its own SessionLocal() directly.
"""

import tempfile
import os
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.document import Document
from app.models.criterion import Criterion
from app.models.evidence import Evidence
from app.services.storage import download_file
from app.services.ocr import extract_text
from app.services.tender_parser import extract_criteria
from app.services.bidder_parser import extract_evidence


def _run_ocr_and_save(document: Document, db) -> str:
    """
    Purpose: Downloads one document's bytes from MinIO, runs OCR/text
    extraction on it, and saves the result directly onto that
    Document row's columns.

    Where it gets its data: document is a Document row already queried
    from the database by the calling task. db is that task's own
    database session.

    Where it's used: Called once per document by both
    process_tender_document() and process_bidder_documents() below --
    the OCR step is identical either way.

    Returns: the extracted text string, so the caller can pass it
    straight into the AI extraction step without re-querying it.
    """
    file_bytes = download_file(document.storage_path)
    is_image = document.mime_type.startswith("image/")
    extension = document.original_filename.rsplit(".", 1)[-1] if "." in document.original_filename else "bin"

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        text, confidence, page_count, is_scanned = extract_text(tmp_path, is_image=is_image)
    finally:
        os.remove(tmp_path)

    document.extracted_text = text
    document.ocr_confidence = confidence
    document.page_count = page_count
    document.is_scanned = is_scanned
    db.commit()

    return text


@celery_app.task(name="process_tender_document")
def process_tender_document(job_id: str):
    """
    Purpose: Background pipeline for a tender's NIT document -- OCR it,
    then extract eligibility criteria from it, then save those as
    Criterion rows for the tender.

    Where it gets its data: job_id is passed in by tenders.py's
    upload_nit_document() endpoint, via .delay(job.id), right after
    the Job row and Document row already exist in the database.

    Where it's used: Queued by routers/tenders.py. Never called
    directly -- always via .delay() so it runs in the Celery worker
    process, not inside the HTTP request.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None:
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        document = db.query(Document).filter(Document.id == job.document_id).first()
        text = _run_ocr_and_save(document, db)

        criteria_data = extract_criteria(text)

        for item in criteria_data:
            db.add(Criterion(
                tender_id=job.tender_id,
                code=item["code"],
                category=item["category"],
                description=item["description"],
                rule_type=item["rule_type"],
                operator=item.get("operator"),
                threshold_json=item.get("threshold_json"),
                mandatory=item["mandatory"],
                evidence_hint=item.get("evidence_hint"),
                msme_exempt=item.get("msme_exempt", False),
            ))

        job.status = JobStatus.DONE
        job.finished_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is not None:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


@celery_app.task(name="process_bidder_documents")
def process_bidder_documents(job_id: str):
    """
    Purpose: Background pipeline for a bidder's submitted documents --
    OCR each one, then match evidence against the tender's already-
    extracted criteria, then save those as Evidence rows.

    Where it gets its data: job_id is passed in by bidders.py's
    upload_bid_documents() endpoint, via .delay(job.id), right after
    the Job row and all Document rows already exist in the database.

    Where it's used: Queued by routers/bidders.py. Never called
    directly -- always via .delay().

    Note: This task creates Evidence rows only -- no Verdict rows.
    Deciding PASS/FAIL/REVIEW from this evidence is the rules engine's
    job, built in Phase 4, not this phase.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None:
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        documents = db.query(Document).filter(Document.bidder_id == job.bidder_id).all()
        documents_for_ai = []
        for document in documents:
            text = _run_ocr_and_save(document, db)
            documents_for_ai.append({"id": document.id, "text": text})

        criteria = db.query(Criterion).filter(Criterion.tender_id == job.tender_id).all()
        criteria_for_ai = [
            {"id": c.id, "code": c.code, "description": c.description, "evidence_hint": c.evidence_hint}
            for c in criteria
        ]

        evidence_data = extract_evidence(documents_for_ai, criteria_for_ai)

        for item in evidence_data:
            db.add(Evidence(
                bidder_id=job.bidder_id,
                criterion_id=item["criterion_id"],
                document_id=item.get("document_id"),
                raw_value=item.get("raw_value"),
                confidence=item["confidence"],
                ai_rationale=item.get("ai_rationale"),
                page_number=item.get("page_number"),
            ))

        job.status = JobStatus.DONE
        job.finished_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is not None:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()