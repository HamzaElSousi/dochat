import os
import sqlite3
from datetime import datetime
from flask import Blueprint, redirect, render_template, url_for, current_app

from ..auth import require_auth

admin_bp = Blueprint('admin', __name__)


def _format_datetime(iso_str: str) -> str:
    """Format ISO-8601 UTC string to 'MMM D, YYYY HH:MM' for display."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime('%b %-d, %Y %H:%M')
    except (ValueError, TypeError):
        return iso_str or ''


@admin_bp.route('/dochat/admin')
@require_auth
def admin_root():
    """Redirect /dochat/admin -> /dochat/admin/docs (per D-03)."""
    return redirect(url_for('admin.admin_docs'))


@admin_bp.route('/dochat/admin/docs')
@require_auth
def admin_docs():
    """Document management page — queries documents table, renders docs.html.

    Documents ordered by uploaded_at descending (most recent first).
    chunk_count comes from documents.chunk_count (denormalized in ingest pipeline).
    """
    conn = current_app.config.get('DB_CONN')
    rows = conn.execute(
        "SELECT id, filename, filetype, uploaded_at, status, chunk_count "
        "FROM documents ORDER BY uploaded_at DESC"
    ).fetchall()

    docs = []
    for row in rows:
        doc_id, filename, filetype, uploaded_at, status, chunk_count = row
        docs.append({
            'doc_id': doc_id,
            'filename': filename,
            'type': filetype,
            'upload_date': uploaded_at,
            'upload_date_display': _format_datetime(uploaded_at),
            'status': status,
            'chunk_count': chunk_count or 0,
        })

    return render_template('admin/docs.html', docs=docs)


@admin_bp.route('/dochat/admin/leads')
@require_auth
def admin_leads():
    """Leads review page — queries leads table, renders leads.html.

    Leads ordered by created_at descending (most recent first).
    Table will be empty until Phase 6 populates it — no error shown (per D-12).
    """
    # Fresh connection — bypasses Passenger's persistent DB_CONN page cache
    db_path = current_app.config.get('DB_PATH')
    fresh = sqlite3.connect(db_path)
    try:
        fresh.execute("PRAGMA journal_mode=WAL")
        fresh.execute("PRAGMA busy_timeout=10000")
        rows = fresh.execute(
            "SELECT id, name, email, question, created_at "
            "FROM leads ORDER BY created_at DESC"
        ).fetchall()
    finally:
        fresh.close()

    leads = []
    for row in rows:
        lead_id, name, email, question, created_at = row
        leads.append({
            'id': lead_id,
            'name': name,
            'email': email,
            'question': question,
            'timestamp': created_at,
            'timestamp_display': _format_datetime(created_at),
        })

    return render_template('admin/leads.html', leads=leads)


@admin_bp.route('/dochat/admin/settings')
@require_auth
def admin_settings():
    """Admin settings page — renders the book-call URL configuration form.

    GET /dochat/admin/settings — protected by @require_auth (D-11).
    Fetches current book_call_url from settings table (empty string if not set).
    """
    # Fresh connection — bypasses Passenger's persistent DB_CONN page cache
    db_path = current_app.config.get('DB_PATH')
    fresh = sqlite3.connect(db_path)
    try:
        fresh.execute("PRAGMA journal_mode=WAL")
        fresh.execute("PRAGMA busy_timeout=10000")
        row = fresh.execute(
            "SELECT value FROM settings WHERE key = ?", ['book_call_url']
        ).fetchone()
    finally:
        fresh.close()
    book_call_url = row[0] if row else ''
    return render_template('admin/settings.html', book_call_url=book_call_url, active_page='settings')
