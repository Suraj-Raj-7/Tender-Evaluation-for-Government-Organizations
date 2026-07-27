"""
backend/app/routers/reports.py
----------------------------------
Purpose: Exposes the PDF export functionality built in
services/report_gen.py as real API endpoints -- the full audit
bundle, the simpler TQ (Technically Qualified) bidder list, and an
HTML preview of the audit bundle for debugging the template without
waiting on a full PDF render.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User, RoleEnum
from app.services.report_gen import generate_audit_bundle, generate_tq_list, generate_audit_bundle_html
from app.services.audit_logger import log_action

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{tender_id}/audit-bundle")
def get_audit_bundle(
    tender_id: int,
    http_request: Request,
    current_user: User = Depends(require_role(RoleEnum.EVALUATOR.value, RoleEnum.AUDITOR.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Generates and returns the full audit bundle PDF for one
    tender -- every criterion, bidder, evidence value, verdict,
    override, and relevant audit log entry.

    Where it gets its data: tender_id from the URL. Everything else
    is gathered inside services/report_gen.py's
    generate_audit_bundle().

    Where it's used: called by the frontend's EvaluationMatrix.jsx
    "Export Audit Bundle" button.
    """
    try:
        pdf_bytes = generate_audit_bundle(tender_id, current_user.full_name, db)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    log_action(
        db,
        user_id=current_user.id,
        action="REPORT_EXPORTED",
        entity_type="tender",
        entity_id=tender_id,
        new_value={"report_type": "audit_bundle"},
        ip_address=http_request.client.host if http_request.client else None,
    )
    db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="audit_bundle_tender_{tender_id}.pdf"'},
    )


@router.get("/{tender_id}/tq-list")
def get_tq_list(
    tender_id: int,
    http_request: Request,
    current_user: User = Depends(require_role(RoleEnum.EVALUATOR.value, RoleEnum.AUDITOR.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Generates and returns the simpler TQ (Technically
    Qualified) bidder list PDF -- company name and GSTIN only, for
    handoff to the financial bid opening stage.

    Where it's used: called by the frontend's EvaluationMatrix.jsx
    "Export TQ List" button.
    """
    try:
        pdf_bytes = generate_tq_list(tender_id, db)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    log_action(
        db,
        user_id=current_user.id,
        action="REPORT_EXPORTED",
        entity_type="tender",
        entity_id=tender_id,
        new_value={"report_type": "tq_list"},
        ip_address=http_request.client.host if http_request.client else None,
    )
    db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="tq_list_tender_{tender_id}.pdf"'},
    )


@router.get("/{tender_id}/preview", response_class=HTMLResponse)
def preview_audit_bundle(
    tender_id: int,
    current_user: User = Depends(require_role(RoleEnum.EVALUATOR.value, RoleEnum.AUDITOR.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Returns the audit bundle as raw HTML instead of a PDF --
    lets a developer check the template renders correctly in a
    browser, without waiting for WeasyPrint's full PDF render each
    time. Does not write a REPORT_EXPORTED audit entry, since this is
    a debugging view, not an official export.

    Where it's used: manual debugging only -- not called by any
    frontend page.
    """
    try:
        html_content = generate_audit_bundle_html(tender_id, current_user.full_name, db)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    return HTMLResponse(content=html_content)