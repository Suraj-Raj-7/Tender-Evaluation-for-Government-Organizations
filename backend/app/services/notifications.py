"""
backend/app/services/notifications.py
------------------------------------------
Purpose: Sends the simultaneous result email to every bidder on a
tender, the moment an Evaluator marks that tender's evaluation
complete. ELIGIBLE bidders get a short confirmation. NOT_ELIGIBLE
bidders get a full criterion-by-criterion breakdown of every
mandatory criterion they failed, including what was required and
what was actually found in their documents.

Why this file exists: bidders must never see an early or partial
verdict -- only the final, official result, and all bidders must be
notified at the same moment (not as individual verdicts happen to
finish). This function is called exactly once per tender, right after
the tender's status flips to TECHNICAL_COMPLETE.

Where it's used: called by workers/tasks.py's send_notifications
Celery task, which is queued by routers/evaluation.py's
mark_evaluation_complete() endpoint.
"""

from app.models.bidder import Bidder, OverallVerdict
from app.models.user import User
from app.models.tender import Tender
from app.models.evidence import Evidence
from app.models.criterion import Criterion
from app.models.verdict import Verdict, VerdictEnum
from app.models.document import Document
from app.services.email_service import send_email
from app.services.audit_logger import log_action


def _get_failed_mandatory_criteria(bidder_id: int, db) -> list[dict]:
    """
    Purpose: Builds the criterion-level failure breakdown for one
    NOT_ELIGIBLE bidder -- every mandatory criterion where the final
    verdict is FAIL, with what was required, what was found, and
    which document it came from.

    Where it gets its data: joins Evidence -> Verdict -> Criterion for
    this bidder, filtered to mandatory criteria with final_verdict ==
    FAIL, plus an outer join to Document for the source filename.

    Where it's used: called once per NOT_ELIGIBLE bidder by
    send_evaluation_notifications() below, to build the email body.
    """
    rows = (
        db.query(Evidence, Verdict, Criterion, Document)
        .join(Verdict, Verdict.evidence_id == Evidence.id)
        .join(Criterion, Evidence.criterion_id == Criterion.id)
        .outerjoin(Document, Document.id == Evidence.document_id)
        .filter(
            Evidence.bidder_id == bidder_id,
            Criterion.mandatory.is_(True),
            Verdict.final_verdict == VerdictEnum.FAIL,
        )
        .all()
    )

    return [
        {
            "code": criterion.code,
            "description": criterion.description,
            "found_value": evidence.raw_value or "Not found",
            "document_name": document.original_filename if document else "N/A",
        }
        for evidence, verdict, criterion, document in rows
    ]


def _build_eligible_email(tender: Tender) -> tuple[str, str]:
    """
    Purpose: Builds the subject and HTML body for a TQ (Technically
    Qualified) bidder's result email.

    Where it's used: called by send_evaluation_notifications() below,
    for every bidder whose overall_verdict is ELIGIBLE.
    """
    subject = f"TenderIQ: You are Technically Qualified -- {tender.name}"
    body = f"""
        <h2>You are Technically Qualified</h2>
        <p>Your submission for <strong>{tender.name}</strong> has passed technical evaluation.</p>
        <p>Please await notification of the financial bid opening.</p>
    """
    return subject, body


def _build_not_eligible_email(tender: Tender, failed_criteria: list[dict]) -> tuple[str, str]:
    """
    Purpose: Builds the subject and HTML body for a TNQ (Technically
    Not Qualified) bidder's result email, including the full
    criterion-by-criterion breakdown of why.

    Where it gets its data: failed_criteria comes from
    _get_failed_mandatory_criteria() above.

    Where it's used: called by send_evaluation_notifications() below,
    for every bidder whose overall_verdict is NOT_ELIGIBLE.
    """
    rows_html = "".join(
        f"""
        <tr>
            <td style="padding:8px;border:1px solid #ddd;">{c['code']}</td>
            <td style="padding:8px;border:1px solid #ddd;">{c['description']}</td>
            <td style="padding:8px;border:1px solid #ddd;">{c['found_value']}</td>
            <td style="padding:8px;border:1px solid #ddd;">{c['document_name']}</td>
        </tr>
        """
        for c in failed_criteria
    )

    subject = f"TenderIQ: Evaluation Result -- {tender.name}"
    body = f"""
        <h2>Technical Evaluation Result</h2>
        <p>Your submission for <strong>{tender.name}</strong> was found <strong>Not Eligible</strong>
        based on the following criteria:</p>
        <table style="border-collapse:collapse;width:100%;">
            <tr style="background:#f0f0f0;">
                <th style="padding:8px;border:1px solid #ddd;">Code</th>
                <th style="padding:8px;border:1px solid #ddd;">Requirement</th>
                <th style="padding:8px;border:1px solid #ddd;">Found</th>
                <th style="padding:8px;border:1px solid #ddd;">Source Document</th>
            </tr>
            {rows_html}
        </table>
        <p>If you believe this evaluation is incorrect, you may raise a grievance from your bidder portal.</p>
    """
    return subject, body


def send_evaluation_notifications(tender_id: int, db) -> None:
    """
    Purpose: The main entry point of this file. Sends one result email
    to every bidder on a tender, and writes a NOTIFICATION_SENT audit
    log entry for each one sent.

    Where it gets its data: tender_id identifies which tender just
    closed. db is the caller's active database session (in practice,
    a Celery task's own session -- see workers/tasks.py).

    Where it's used: called by workers/tasks.py's send_notifications
    Celery task.

    Note: skips (with a console log, not a crash) any bidder with no
    linked user account, or whose overall_verdict is neither ELIGIBLE
    nor NOT_ELIGIBLE (e.g. a bidder who applied but never submitted
    any documents, still PENDING) -- one bidder's incomplete data must
    never stop every other bidder on the tender from being notified.
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        print(f"[notifications.py] Tender {tender_id} not found -- cannot send notifications")
        return

    bidders = db.query(Bidder).filter(Bidder.tender_id == tender_id).all()

    for bidder in bidders:
        if bidder.user_id is None:
            print(f"[notifications.py] Bidder {bidder.id} has no linked user account -- skipping")
            continue

        user = db.query(User).filter(User.id == bidder.user_id).first()
        if user is None:
            print(f"[notifications.py] Bidder {bidder.id}'s user {bidder.user_id} not found -- skipping")
            continue

        if bidder.overall_verdict == OverallVerdict.ELIGIBLE:
            subject, body = _build_eligible_email(tender)
        elif bidder.overall_verdict == OverallVerdict.NOT_ELIGIBLE:
            failed_criteria = _get_failed_mandatory_criteria(bidder.id, db)
            subject, body = _build_not_eligible_email(tender, failed_criteria)
        else:
            print(
                f"[notifications.py] Bidder {bidder.id} has overall_verdict="
                f"{bidder.overall_verdict.value}, not ELIGIBLE/NOT_ELIGIBLE -- skipping"
            )
            continue

        sent = send_email(to_email=user.email, subject=subject, html_body=body)

        if sent:
            log_action(
                db,
                user_id=None,  # system-triggered, not a specific logged-in user's action
                action="NOTIFICATION_SENT",
                entity_type="bidder",
                entity_id=bidder.id,
                new_value={"overall_verdict": bidder.overall_verdict.value, "email": user.email},
            )

    db.commit()