"""
backend/app/services/report_gen.py
------------------------------------------
Purpose: Gathers all data for one tender out of the database and
renders it into PDF documents using WeasyPrint: a full audit bundle
(every criterion, bidder, evidence value, verdict, override, and
audit log entry) and a simple TQ (Technically Qualified) bidder list
for handoff to the financial bid stage.

Why this file exists: neither the database rows nor the Jinja2
template know how to talk to each other directly. This file queries
everything needed, reshapes it into plain, template-friendly data
(real string values, not raw SQLAlchemy enum objects -- Jinja2 would
otherwise print "VerdictEnum.PASS" instead of "PASS"), and calls
WeasyPrint to produce PDF bytes.

Where it's used: called by routers/reports.py's three endpoints
(audit-bundle, tq-list, preview).
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.models.tender import Tender
from app.models.criterion import Criterion
from app.models.bidder import Bidder, OverallVerdict
from app.models.evidence import Evidence
from app.models.verdict import Verdict, Override
from app.models.user import User
from app.models.audit import AuditLog


_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)))


def _criterion_sort_key(code: str):
    """
    Purpose: Sort key that puts criterion codes like "C1", "C2", ...
    "C37" in correct numeric order. Plain string sorting would put
    "C10" before "C2" (alphabetical), which reads as visibly wrong in
    a legal document once a tender has more than 9 criteria.

    Where it's used: called wherever criteria/evidence need to be
    listed in code order below.
    """
    match = re.match(r"^(\D*)(\d+)$", code or "")
    if match:
        return (match.group(1), int(match.group(2)))
    return (code or "", 0)


def _build_bidder_context(bidder: Bidder, criteria: list[Criterion], db) -> dict:
    """
    Purpose: Builds one bidder's full evidence/verdict detail --
    every criterion's extracted value, confidence, AI verdict, final
    verdict, and override status -- shaped for direct use in the
    Jinja2 template's per-bidder section and summary matrix.

    Where it gets its data: joins Evidence -> Verdict for this
    bidder, matched against the tender's full criteria list.

    Where it's used: called once per bidder by
    _gather_audit_bundle_data() below.
    """
    evidence_rows = (
        db.query(Evidence, Verdict)
        .join(Verdict, Verdict.evidence_id == Evidence.id)
        .filter(Evidence.bidder_id == bidder.id)
        .all()
    )

    criteria_by_id = {c.id: c for c in criteria}
    evidence_by_code = {}
    evidence_list = []

    for evidence, verdict in evidence_rows:
        criterion = criteria_by_id.get(evidence.criterion_id)
        if criterion is None:
            continue

        entry = {
            "criterion_code": criterion.code,
            "criterion_description": criterion.description,
            "raw_value": evidence.raw_value,
            "confidence": evidence.confidence,
            "ai_verdict": verdict.ai_verdict.value,
            "final_verdict": verdict.final_verdict.value,
            "is_overridden": verdict.is_overridden,
            "ai_rationale": evidence.ai_rationale,
        }
        evidence_by_code[criterion.code] = entry
        evidence_list.append(entry)

    evidence_list.sort(key=lambda e: _criterion_sort_key(e["criterion_code"]))

    return {
        "company_name": bidder.company_name,
        "category": bidder.category.value,
        "overall_verdict": bidder.overall_verdict.value,
        "evidence_by_code": evidence_by_code,
        "evidence_list": evidence_list,
    }


def _build_overrides_context(tender_id: int, db) -> list[dict]:
    """
    Purpose: Builds the full override history for every bidder on
    this tender, with the officer's real name resolved (Override only
    stores officer_id) -- shaped for the template's "Override Records"
    section.

    Where it gets its data: joins Override -> Verdict -> Evidence ->
    Bidder (to scope to this tender), plus User (to resolve
    officer_id into a readable name).

    Where it's used: called once by _gather_audit_bundle_data() below.
    """
    rows = (
        db.query(Override, User)
        .join(User, User.id == Override.officer_id)
        .join(Verdict, Verdict.id == Override.verdict_id)
        .join(Evidence, Evidence.id == Verdict.evidence_id)
        .join(Bidder, Bidder.id == Evidence.bidder_id)
        .filter(Bidder.tender_id == tender_id)
        .order_by(Override.overridden_at.asc())
        .all()
    )

    return [
        {
            "overridden_at": override.overridden_at.strftime("%Y-%m-%d %H:%M:%S"),
            "officer_name": user.full_name,
            "from_verdict": override.from_verdict.value,
            "to_verdict": override.to_verdict.value,
            "reason": override.reason,
        }
        for override, user in rows
    ]


def _build_audit_entries_context(tender_id: int, db) -> list[dict]:
    """
    Purpose: Builds the relevant audit log entries for this tender's
    PDF -- entries directly tied to the tender itself, plus entries
    tied to any of its bidders -- so a reader sees the full action
    trail without needing separate database access.

    Where it gets its data: AuditLog rows where entity_type="tender"
    and entity_id=tender_id, combined with rows tied to this tender's
    bidder IDs.

    Where it's used: called once by _gather_audit_bundle_data() below.
    """
    tender_entries = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "tender", AuditLog.entity_id == tender_id)
        .all()
    )

    bidder_ids = [b.id for b in db.query(Bidder.id).filter(Bidder.tender_id == tender_id).all()]
    bidder_entries = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "bidder", AuditLog.entity_id.in_(bidder_ids))
        .all()
        if bidder_ids else []
    )

    all_entries = sorted(tender_entries + bidder_entries, key=lambda e: e.timestamp)

    return [
        {
            "timestamp": entry.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": entry.user_id,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
        }
        for entry in all_entries
    ]


def _gather_audit_bundle_data(tender_id: int, generated_by: str, db) -> dict:
    """
    Purpose: Assembles every piece of data audit_report.html needs, as
    plain dicts/strings -- no raw SQLAlchemy enum objects passed to
    the template.

    Where it gets its data: tender_id identifies which tender to
    report on. generated_by is the display name of whoever requested
    the export (from the calling router's current_user).

    Where it's used: called by generate_audit_bundle() and
    generate_audit_bundle_html() below.

    Raises: ValueError if the tender doesn't exist -- the calling
    router turns this into a 404.
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        raise ValueError(f"Tender {tender_id} not found")

    criteria = db.query(Criterion).filter(Criterion.tender_id == tender_id).all()
    criteria.sort(key=lambda c: _criterion_sort_key(c.code))

    bidders = db.query(Bidder).filter(Bidder.tender_id == tender_id).all()

    return {
        "tender": {
            "id": tender.id,
            "name": tender.name,
            "description": tender.description,
            "estimated_value": tender.estimated_value,
            "deadline": tender.deadline.strftime("%Y-%m-%d %H:%M"),
            "status": tender.status.value,
            "created_at": tender.created_at.strftime("%Y-%m-%d %H:%M"),
        },
        "criteria": [
            {
                "code": c.code,
                "category": c.category.value,
                "description": c.description,
                "mandatory": c.mandatory,
            }
            for c in criteria
        ],
        "bidders": [_build_bidder_context(b, criteria, db) for b in bidders],
        "overrides": _build_overrides_context(tender_id, db),
        "audit_entries": _build_audit_entries_context(tender_id, db),
        "generated_by": generated_by,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def generate_audit_bundle(tender_id: int, generated_by: str, db) -> bytes:
    """
    Purpose: Main entry point for the full audit bundle PDF. Gathers
    all data for the tender, renders audit_report.html with it, and
    converts the result to PDF bytes via WeasyPrint.

    Where it's used: called by routers/reports.py's
    GET /reports/{tender_id}/audit-bundle endpoint.

    Raises: ValueError if the tender doesn't exist.
    """
    context = _gather_audit_bundle_data(tender_id, generated_by, db)
    template = _jinja_env.get_template("audit_report.html")
    html_content = template.render(**context)
    return HTML(string=html_content).write_pdf()


def generate_audit_bundle_html(tender_id: int, generated_by: str, db) -> str:
    """
    Purpose: Same data as generate_audit_bundle(), but returns the
    raw rendered HTML instead of a PDF -- useful for checking the
    template renders correctly in a browser without waiting for a
    full PDF render each time.

    Where it's used: called by routers/reports.py's
    GET /reports/{tender_id}/preview endpoint.
    """
    context = _gather_audit_bundle_data(tender_id, generated_by, db)
    template = _jinja_env.get_template("audit_report.html")
    return template.render(**context)


def generate_tq_list(tender_id: int, db) -> bytes:
    """
    Purpose: Generates a simple PDF listing only the Technically
    Qualified (ELIGIBLE) bidders for a tender -- company name and
    GSTIN only -- for handoff to the financial bid opening stage.

    Where it's used: called by routers/reports.py's
    GET /reports/{tender_id}/tq-list endpoint.

    Raises: ValueError if the tender doesn't exist.
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        raise ValueError(f"Tender {tender_id} not found")

    eligible_bidders = (
        db.query(Bidder)
        .filter(Bidder.tender_id == tender_id, Bidder.overall_verdict == OverallVerdict.ELIGIBLE)
        .all()
    )

    rows_html = "".join(
        f"<tr><td>{b.company_name}</td><td>{b.gstin or 'N/A'}</td></tr>"
        for b in eligible_bidders
    )

    html_content = f"""
    <html><head><meta charset="utf-8"><style>
        body {{ font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 12px; }}
        h1 {{ font-size: 18px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
        th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
        th {{ background: #ECEFF3; }}
    </style></head><body>
        <h1>Technically Qualified Bidders</h1>
        <p><strong>Tender:</strong> {tender.name}</p>
        <p><strong>Total TQ Bidders:</strong> {len(eligible_bidders)}</p>
        <table>
            <tr><th>Company Name</th><th>GSTIN</th></tr>
            {rows_html if rows_html else '<tr><td colspan="2">No bidders were found eligible.</td></tr>'}
        </table>
    </body></html>
    """
    return HTML(string=html_content).write_pdf()