"""
backend/app/services/audit_logger.py
------------------------------------------
Purpose: The single shared function every router/service calls to
write one AuditLog row. Centralizes audit logging so every part of
the platform records actions the same way, with the same safety
guarantee.

Why this file exists: Before Phase 6, only evaluation.py's override
endpoint wrote to AuditLog, and it did so with an inline db.add(...)
call. Phase 6 needs many more actions logged (login, document views,
tender creation, evaluation complete, notifications sent, report
exports, grievances submitted). Rather than repeat "build an AuditLog
row" logic in every router, this file is the one place that knows how.

CRITICAL SAFETY RULE:
An audit log write must NEVER be allowed to break the real action it's
recording. If write history logging today caused the underlying login/
override/upload to fail, an audit table problem would take down the
entire platform's actual functionality -- clearly wrong for a
supporting record-keeping feature. So this function catches every
exception itself, prints the error to the server console for
visibility, and always returns normally either way.

Where it's used: Called from routers throughout the codebase (auth.py,
tenders.py, bidders.py, documents.py, evaluation.py, reports.py,
grievances.py, admin.py) anywhere a significant action happens.

Note on transactions: this function calls db.flush() (to catch DB-level
errors immediately) but deliberately does NOT call db.commit(). The
calling router is expected to commit as part of its own transaction,
usually right alongside the real change being made -- so the audit
row and the actual change succeed or fail together, atomically.
"""

from app.models.audit import AuditLog


def log_action(
    db,
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Purpose: Writes one AuditLog row describing a significant action
    taken on the platform. This is the ONLY function anywhere in the
    codebase that should construct an AuditLog row directly -- every
    router calls this instead of building one inline.

    Where it gets its data: user_id and ip_address usually come from
    the calling router's current_user and http_request.client.host.
    action is a short fixed string the caller chooses (e.g.
    "VERDICT_OVERRIDE", "LOGIN", "DOCUMENT_VIEWED").
    entity_type/entity_id identify which record the action relates to
    (e.g. entity_type="tender", entity_id=7). old_value/new_value are
    optional JSON-serializable snapshots, used for actions like
    overrides where "what changed" matters.

    Where it's used: Called by routers immediately before or after
    they commit the actual change they're making -- e.g. auth.py calls
    this after a successful login, evaluation.py calls this after
    building an Override row, reports.py calls this after generating a
    PDF export.

    Never raises: any database error while writing the audit row is
    caught here, printed to the server console, and swallowed --
    the calling router's real operation must be able to proceed (or
    fail on its own terms) regardless of whether this logging
    succeeded.
    """
    try:
        db.add(AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
        ))
        # flush (not commit) so a DB-level error -- e.g. a foreign key
        # violation -- surfaces here and is caught, instead of only
        # appearing later at the caller's own db.commit().
        db.flush()
    except Exception as e:
        # Per this file's safety rule: never let an audit logging
        # failure take down the real action being performed.
        print(f"[audit_logger.py] Failed to write audit log entry "
              f"(action={action}, user_id={user_id}): {e}")