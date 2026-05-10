import os
import re
from flask import Blueprint, request, jsonify, current_app

from ..services.query import handle_chat

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE
)

chat_bp = Blueprint('chat', __name__)

# Read ALLOWED_ORIGINS once at module load.
# Each element is a stripped origin string, e.g. "https://social-automate.com".
# Empty string in env var or missing var → no origins allowed → no CORS headers added.
_ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get('ALLOWED_ORIGINS', '').split(',')
    if o.strip()
]


def _cors_headers(origin: str) -> dict:
    """Return CORS response headers if origin is in the allowlist, else empty dict.

    Implements D-08: only listed domains receive Access-Control-Allow-Origin.
    Admin routes (/admin/*) are NOT affected — this helper is only used in /chat.
    """
    if origin in _ALLOWED_ORIGINS:
        return {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
    return {}


@chat_bp.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    """Public chat endpoint — no authentication required (D-04).

    POST body: {"message": "...", "session_id": "..."}  (session_id optional, D-05)
    Response:  {"answer": "...", "session_id": "...", "fallback": bool,
                "sources": [...], "chips": ["Q1", "Q2", "Q3"]}
               chips is [] when fallback=true or when chip parsing fails (D-07).
    """
    origin = request.headers.get('Origin', '')
    cors = _cors_headers(origin)

    # Handle CORS preflight (OPTIONS) — return 204 with CORS headers (D-08)
    if request.method == 'OPTIONS':
        return ('', 204, cors)

    conn = current_app.config.get('DB_CONN')

    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        resp = jsonify({'error': "Missing required field: 'message'"})
        resp.headers.update(cors)
        return resp, 400

    MAX_MESSAGE_LEN = int(os.environ.get('MAX_MESSAGE_LEN', '2000'))
    if len(message) > MAX_MESSAGE_LEN:
        resp = jsonify({'error': 'Message too long'})
        resp.headers.update(cors)
        return resp, 400

    # session_id is optional — None signals new session (D-05)
    # Validate UUID v4 format to prevent session fixation / injection (CR-03)
    session_id_raw = data.get('session_id') or None
    session_id = session_id_raw if (session_id_raw and _UUID_RE.match(session_id_raw)) else None

    try:
        result = handle_chat(conn, message, session_id)
        resp = jsonify(result)
        resp.headers.update(cors)
        return resp, 200
    except Exception:
        # handle_chat() is designed to never raise, but guard defensively.
        # Never expose stack traces to the client (T-03-03 pattern).
        resp = jsonify({'error': 'Internal server error'})
        resp.headers.update(cors)
        return resp, 500
