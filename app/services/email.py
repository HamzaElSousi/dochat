"""Lead notification email service.

Sends a plain-text SMTP email to admin when a new lead is captured.
Failure is non-fatal per D-08 — caller must still save the lead to DB.
"""
import os
import sys
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage


def send_lead_notification(
    name: str,
    email: str,
    phone: str,
    question: str,
    timestamp: str,
) -> bool:
    """Send a plain-text lead notification email to ADMIN_EMAIL via SMTP.

    Returns True on success, False on any failure.
    On failure, logs the exception message to stderr (non-fatal per D-08).

    Env vars required:
      SMTP_HOST     — outgoing SMTP server hostname (e.g. smtp.siteground.com)
      SMTP_PORT     — SMTP port as integer string (e.g. 587 for STARTTLS, 465 for SSL)
      SMTP_USER     — SMTP login username (usually the sender email)
      SMTP_PASS     — SMTP password
      ADMIN_EMAIL   — recipient address for lead notifications
    """
    smtp_host = os.environ.get('SMTP_HOST', '')
    smtp_port_str = os.environ.get('SMTP_PORT', '587')
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    admin_email = os.environ.get('ADMIN_EMAIL', '')

    if not all([smtp_host, smtp_user, smtp_pass, admin_email]):
        print(
            '[DocChat] SMTP not configured — skipping lead notification email',
            file=sys.stderr,
        )
        return False

    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        print(
            f'[DocChat] Invalid SMTP_PORT "{smtp_port_str}" — skipping email',
            file=sys.stderr,
        )
        return False

    # Subject: "New DocChat Lead: <first 60 chars of question>" (D-07)
    subject_snippet = question[:60].rstrip()
    subject = f'New DocChat Lead: {subject_snippet}'

    # Plain-text body with all lead fields (D-07)
    body = (
        f'New lead captured via DocChat\n'
        f'================================\n'
        f'Name:      {name}\n'
        f'Email:     {email}\n'
        f'Phone:     {phone or "(not provided)"}\n'
        f'Question:  {question}\n'
        f'Timestamp: {timestamp}\n'
    )

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = admin_email
    msg.set_content(body)

    try:
        # Use SMTP_SSL for port 465, STARTTLS for all others
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        return True
    except Exception as exc:
        # Non-fatal per D-08 — log to stderr, caller still saves lead to DB
        print(f'[DocChat] SMTP error — lead saved but email not sent: {exc}', file=sys.stderr)
        return False
