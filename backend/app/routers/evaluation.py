"""
backend/app/routers/evaluation.py
-------------------------------------
Purpose: The core Phase 4 API surface for Evaluators -- the evaluation
matrix (the full grid every officer works from), evidence detail for
one cell, the override endpoint (change any AI verdict with a
mandatory reason), and marking a tender's evaluation officially
complete.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User, RoleEnum
from app.models.tender import Tender, TenderStatus
from app.models.criterion import Criterion
from app.models.bidder import Bidder
from app.models.evidence import Evidence
from app.models.document import Document
from app.models.verdict import Verdict, Override, VerdictEnum
from app.services.audit_logger import log_action
from app.schemas.evaluation import (
    MatrixResponse, MatrixCriterion, MatrixBidder, MatrixCell,
    EvidenceDetailResponse, OverrideHistoryItem,
)
from app.schemas.verdict import OverrideRequest, VerdictResponse
from app.models.job import Job, JobType, JobStatus
from app.services.rules_engine import calculate_overall_verdict
from app.workers.tasks import send_notifications, process_bidder_documents

router = APIRouter(tags=["evaluation"])


@router.get("/tenders/{tender_id}/matrix", response_model=MatrixResponse)
def get_evaluation_matrix(
    tender_id: int,
    current_user: User = Depends(require_role(RoleEnum.EVALUATOR.value, RoleEnum.AUDITOR.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Builds the entire evaluation grid -- every bidder as a
    row, every criterion as a column -- in one call, so the frontend's
    EvaluationMatrix page (Phase 5) doesn't need N+1 requests.

    Where it gets its data: tender_id from the URL. Queries every
    Criterion for this tender, every Bidder who applied, and every
    Evidence+Verdict+Document row for those bidders.

    Where it's used: Called once when the Evaluator opens a tender's
    matrix page, and again after any override to refresh the grid.
    """
    criteria = db.query(Criterion).filter(Criterion.tender_id == tender_id).all()
    bidders = db.query(Bidder).filter(Bidder.tender_id == tender_id).all()

    matrix_bidders = []
    for bidder in bidders:
        evidence_rows = (
            db.query(Evidence, Verdict, Document)
            .join(Verdict, Verdict.evidence_id == Evidence.id)
            .outerjoin(Document, Document.id == Evidence.document_id)
            .filter(Evidence.bidder_id == bidder.id)
            .all()
        )

        cells: dict[str, MatrixCell] = {}
        for evidence, verdict, document in evidence_rows:
            criterion = next((c for c in criteria if c.id == evidence.criterion_id), None)
            if criterion is None:
                continue
            cells[criterion.code] = MatrixCell(
                evidence_id=evidence.id,
                raw_value=evidence.raw_value,
                confidence=evidence.confidence,
                ai_verdict=verdict.ai_verdict,
                final_verdict=verdict.final_verdict,
                is_overridden=verdict.is_overridden,
                ai_rationale=evidence.ai_rationale,
                document_id=evidence.document_id,
                page_number=evidence.page_number,
                doc_name=document.original_filename if document else None,
            )

        matrix_bidders.append(MatrixBidder(
            id=bidder.id,
            company_name=bidder.company_name,
            category=bidder.category,
            overall_verdict=bidder.overall_verdict,
            evidence=cells,
        ))

    matrix_criteria = [
        MatrixCriterion(
            id=c.id, code=c.code, description=c.description,
            category=c.category, mandatory=c.mandatory,
        )
        for c in criteria
    ]

    return MatrixResponse(criteria=matrix_criteria, bidders=matrix_bidders)


@router.get("/evidence/{evidence_id}", response_model=EvidenceDetailResponse)
def get_evidence_detail(
    evidence_id: int,
    current_user: User = Depends(require_role(RoleEnum.EVALUATOR.value, RoleEnum.AUDITOR.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Full detail for one evidence cell -- everything the
    Evidence Panel (Phase 5) needs: the raw AI finding, its verdict,
    and every override ever made to that verdict, in chronological
    order.

    Where it gets its data: evidence_id from the URL. Joins Evidence ->
    Verdict -> Criterion -> Document -> Override.
    """
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")

    verdict = db.query(Verdict).filter(Verdict.evidence_id == evidence.id).first()
    if verdict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verdict not found for this evidence")

    criterion = db.query(Criterion).filter(Criterion.id == evidence.criterion_id).first()
    document = (
        db.query(Document).filter(Document.id == evidence.document_id).first()
        if evidence.document_id else None
    )
    overrides = (
        db.query(Override)
        .filter(Override.verdict_id == verdict.id)
        .order_by(Override.overridden_at.asc())
        .all()
    )

    return EvidenceDetailResponse(
        evidence_id=evidence.id,
        criterion_code=criterion.code if criterion else "",
        criterion_description=criterion.description if criterion else "",
        raw_value=evidence.raw_value,
        confidence=evidence.confidence,
        ai_rationale=evidence.ai_rationale,
        document_id=evidence.document_id,
        doc_name=document.original_filename if document else None,
        page_number=evidence.page_number,
        extracted_at=evidence.extracted_at,
        verdict_id=verdict.id,
        ai_verdict=verdict.ai_verdict,
        final_verdict=verdict.final_verdict,
        is_overridden=verdict.is_overridden,
        override_history=[OverrideHistoryItem.model_validate(o) for o in overrides],
    )


@router.post("/verdicts/{verdict_id}/override", response_model=VerdictResponse)
def override_verdict(
    verdict_id: int,
    request: OverrideRequest,
    http_request: Request,
    current_user: User = Depends(require_role(RoleEnum.EVALUATOR.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Lets an Evaluator change any AI verdict, in any direction,
    with a mandatory written reason (min 10 chars, enforced by
    OverrideRequest) -- creates a permanent Override row (never
    edits/deletes one) and updates the Verdict's final_verdict. Then
    recalculates the bidder's overall verdict, since one changed
    criterion can flip ELIGIBLE/NOT_ELIGIBLE/MANUAL_REVIEW.

    Where it gets its data: verdict_id from the URL. request.to_verdict
    and request.reason come from the Evaluator's OverrideForm (Phase
    5). current_user identifies who's overriding. http_request.client
    captures the officer's IP for the permanent audit record (spec 12.3).

    Where it's used: Called from the Evidence Panel's OverrideForm.
    """
    verdict = db.query(Verdict).filter(Verdict.id == verdict_id).first()
    if verdict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verdict not found")

    override = Override(
        verdict_id=verdict.id,
        officer_id=current_user.id,
        from_verdict=verdict.final_verdict,
        to_verdict=request.to_verdict,
        reason=request.reason,
        ip_address=http_request.client.host if http_request.client else None,
    )
    db.add(override)

    verdict.final_verdict = request.to_verdict
    verdict.is_overridden = True

    # Phase Guide exit condition: every override must be independently
    # auditable, not just visible via the Override table -- this is
    # what makes the platform's decision trail legally defensible.
    log_action(
        db,
        user_id=current_user.id,
        action="VERDICT_OVERRIDE",
        entity_type="verdict",
        entity_id=verdict.id,
        old_value={"final_verdict": override.from_verdict.value},
        new_value={"final_verdict": override.to_verdict.value},
        ip_address=http_request.client.host if http_request.client else None,
    )

    db.commit()
    db.refresh(verdict)

    evidence = db.query(Evidence).filter(Evidence.id == verdict.evidence_id).first()
    if evidence is not None:
        calculate_overall_verdict(evidence.bidder_id, db)

    return verdict


@router.post("/tenders/{tender_id}/begin-evaluation")
def begin_evaluation(
    tender_id: int,
    http_request: Request,
    current_user: User = Depends(require_role(RoleEnum.EVALUATOR.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Starts a tender's technical evaluation -- the moment AI
    evidence extraction actually happens, deliberately deferred from
    upload time until now (see routers/bidders.py's upload endpoint,
    which just saves files and does nothing else). Queues one
    independent background job per bidder, so one bidder's OCR/AI
    failure can never block or delay any other bidder's evaluation.

    Where it gets its data: tender_id from the URL. Queries every
    Bidder row for this tender.

    Where it's used: called by the frontend's "Begin Evaluation"
    button on EvaluationMatrix.jsx, shown only once the tender's
    deadline has passed and evaluation hasn't started yet.

    Note: this does not wait for any bidder's processing to finish --
    it queues every job and returns immediately with the list of job
    IDs, so the frontend can poll them.
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    if datetime.now(timezone.utc) < tender.deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot begin evaluation before the submission deadline "
                f"({tender.deadline.isoformat()}) -- bidders may still apply and upload documents."
            ),
        )

    if tender.status not in (TenderStatus.PUBLISHED, TenderStatus.CORRIGENDUM_ISSUED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot begin evaluation -- tender status is currently {tender.status.value}",
        )

    bidders = db.query(Bidder).filter(Bidder.tender_id == tender_id).all()

    tender.status = TenderStatus.EVALUATION

    job_ids = []
    for bidder in bidders:
        job = Job(
            tender_id=tender_id, bidder_id=bidder.id,
            type=JobType.BIDDER_EXTRACTION, status=JobStatus.PENDING,
        )
        db.add(job)
        db.flush()  # assigns job.id
        job_ids.append(job.id)

    log_action(
        db,
        user_id=current_user.id,
        action="EVALUATION_BEGUN",
        entity_type="tender",
        entity_id=tender.id,
        new_value={"bidder_count": len(bidders)},
        ip_address=http_request.client.host if http_request.client else None,
    )
    db.commit()

    # Queue every bidder's processing AFTER commit -- the Celery
    # worker runs in a separate process with its own DB session, so
    # it must only ever see the tender's final, saved EVALUATION
    # status and each Job row that's actually been committed.
    for job_id in job_ids:
        process_bidder_documents.delay(job_id)

    return {
        "message": f"Evaluation begun for {len(bidders)} bidder(s)",
        "tender_id": tender_id,
        "job_ids": job_ids,
    }


@router.post("/tenders/{tender_id}/bidders/{bidder_id}/re-evaluate")
def re_evaluate_bidder(
    tender_id: int,
    bidder_id: int,
    http_request: Request,
    current_user: User = Depends(require_role(RoleEnum.EVALUATOR.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Re-runs AI evidence extraction for exactly one bidder --
    e.g. after their initial run failed, or the Evaluator wants a
    fresh pass. Reuses the exact same process_bidder_documents Celery
    task as begin_evaluation() above, just for a single bidder rather
    than every bidder on the tender. Safe to call repeatedly: any
    criterion the Evaluator has already manually overridden is always
    skipped and never regenerated (see process_one_bidder() in
    workers/tasks.py).

    Where it gets its data: tender_id and bidder_id from the URL.

    Where it's used: called by the frontend's per-bidder "Re-evaluate"
    button on EvaluationMatrix.jsx.
    """
    bidder = db.query(Bidder).filter(Bidder.id == bidder_id, Bidder.tender_id == tender_id).first()
    if bidder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bidder not found on this tender")

    job = Job(
        tender_id=tender_id, bidder_id=bidder_id,
        type=JobType.BIDDER_EXTRACTION, status=JobStatus.PENDING,
    )
    db.add(job)
    db.flush()

    log_action(
        db,
        user_id=current_user.id,
        action="BIDDER_RE_EVALUATED",
        entity_type="bidder",
        entity_id=bidder_id,
        ip_address=http_request.client.host if http_request.client else None,
    )
    db.commit()

    process_bidder_documents.delay(job.id)

    return {"message": f"Re-evaluation started for {bidder.company_name}", "job_id": job.id}


@router.post("/tenders/{tender_id}/complete")
def mark_evaluation_complete(
    tender_id: int,
    http_request: Request,
    current_user: User = Depends(require_role(RoleEnum.EVALUATOR.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Officially closes a tender's technical evaluation. Blocked
    if any mandatory criterion still shows REVIEW for any bidder --
    every REVIEW case must be resolved (via override or otherwise) first.

    Where it gets its data: tender_id from the URL.

    Note: Per spec 5.1, bidder notifications fire simultaneously only
    when this happens -- that notification service is built in Phase
    6. This endpoint only flips the tender's status; it deliberately
    does not send any notifications yet (out of this phase's scope).
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    if tender.status == TenderStatus.TECHNICAL_COMPLETE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This tender's evaluation has already been marked complete",
        )

    if datetime.now(timezone.utc) < tender.deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot mark evaluation complete before the submission deadline "
                f"({tender.deadline.isoformat()}) -- more bidders may still apply."
            ),
        )

    unresolved_review_exists = (
        db.query(Verdict)
        .join(Evidence, Verdict.evidence_id == Evidence.id)
        .join(Criterion, Evidence.criterion_id == Criterion.id)
        .join(Bidder, Evidence.bidder_id == Bidder.id)
        .filter(
            Bidder.tender_id == tender_id,
            Criterion.mandatory.is_(True),
            Verdict.final_verdict == VerdictEnum.REVIEW,
        )
        .first()
        is not None
    )
    if unresolved_review_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resolve all REVIEW cases before marking complete",
        )

    tender.status = TenderStatus.TECHNICAL_COMPLETE

    log_action(
        db,
        user_id=current_user.id,
        action="EVALUATION_COMPLETE",
        entity_type="tender",
        entity_id=tender.id,
        ip_address=http_request.client.host if http_request.client else None,
    )
    db.commit()

    send_notifications.delay(tender.id)

    return {"message": "Evaluation marked complete", "tender_id": tender_id, "status": tender.status.value}