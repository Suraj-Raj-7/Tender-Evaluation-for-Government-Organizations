"""
backend/app/routers/documents.py
------------------------------------
Purpose: Securely serves an uploaded document's actual file bytes back
to the browser, and lists all documents belonging to a bidder.

Why this file exists: Files live in MinIO, not on our server directly.
This is the only place that checks "is this person allowed to see this
specific file?" before streaming it back -- so a bidder can never see
another bidder's documents.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from io import BytesIO
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, RoleEnum
from app.models.document import Document
from app.models.bidder import Bidder
from app.schemas.document import DocumentResponse
from app.services.storage import download_file

router = APIRouter(tags=["documents"])


@router.get("/documents/{document_id}")
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Purpose: Streams a document's real file bytes back to the browser,
    after checking the requester is allowed to see it.

    Where it gets its data: document_id from the URL. current_user from
    the JWT token (who's asking).

    Access rule: BIDDER can only view documents belonging to their own
    Bidder row. EVALUATOR/AUDITOR/PUBLISHER/SYSTEM_ADMIN can view any
    document (per spec 2.4 -- evaluators need full document access to
    review evidence).
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if current_user.role == RoleEnum.BIDDER:
        bidder = db.query(Bidder).filter(
            Bidder.id == document.bidder_id, Bidder.user_id == current_user.id
        ).first()
        if bidder is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not permitted to view this document",
            )

    file_bytes = download_file(document.storage_path)

    # NOTE: Writing DOCUMENT_VIEWED to the audit log is part of Phase 6's
    # audit_logger.py service, which doesn't exist yet -- deferred to
    # that phase, per staying within this phase's scope.
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=document.mime_type,
        headers={"Content-Disposition": f'inline; filename="{document.original_filename}"'},
    )


@router.get("/bidders/{bidder_id}/documents", response_model=list[DocumentResponse])
def list_bidder_documents(
    bidder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Purpose: Lists metadata (not file bytes) for every document a
    specific bidder has uploaded.

    Access rule: same as get_document above -- a BIDDER can only list
    their own documents.
    """
    if current_user.role == RoleEnum.BIDDER:
        bidder = db.query(Bidder).filter(
            Bidder.id == bidder_id, Bidder.user_id == current_user.id
        ).first()
        if bidder is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not permitted to view these documents",
            )

    return db.query(Document).filter(Document.bidder_id == bidder_id).all()