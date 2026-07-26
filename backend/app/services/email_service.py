"""
backend/app/services/email_service.py
------------------------------------------
Purpose: The single, low-level place in the codebase that knows how to
actually send an email over SMTP. Every other service that needs to
send an email (account creation, password reset, evaluation-complete
notifications) calls send_email() here -- none of them import smtplib
directly.

Why this file exists: keeping SMTP connection details in one place
means switching email providers later (e.g. from a local test sandbox
to a real production sender) only requires changing 5 config values
in .env -- no code in this file, or in anything that calls it, needs
to change.

Where it's used: called by services/notifications.py (evaluation
result emails) and routers/admin.py (officer account creation and
password reset emails).
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Purpose: Sends one HTML email over SMTP, using the credentials
    configured in settings (config.py, sourced from .env).

    Where it gets its data: to_email/subject/html_body are built by
    the caller (e.g. notifications.py builds the evaluation-result
    email content, admin.py builds the account-credentials email
    content) -- this function only handles the actual sending.

    Where it's used: called by services/notifications.py and
    routers/admin.py.

    Returns: True if the send succeeded, False if it failed for any
    reason. Never raises -- a failed email must not crash the calling
    request (e.g. an officer account should still be created even if,
    for some reason, the welcome email couldn't be delivered).
    """
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME:
        print(f"[email_service.py] SMTP not configured -- skipping email to {to_email}")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM
    message["To"] = to_email
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [to_email], message.as_string())
        print(f"[email_service.py] Sent email to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"[email_service.py] Failed to send email to {to_email}: {e}")
        return False