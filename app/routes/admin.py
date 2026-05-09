from flask import Blueprint, redirect, url_for
from ..auth import require_auth

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/dochat/admin')
@require_auth
def admin_root():
    """Redirect /dochat/admin -> /dochat/admin/docs (D-03)."""
    return redirect(url_for('admin.admin_docs'))


@admin_bp.route('/dochat/admin/docs')
@require_auth
def admin_docs():
    """Document management page -- stub, Plan 02 replaces body."""
    return 'Coming soon', 200


@admin_bp.route('/dochat/admin/leads')
@require_auth
def admin_leads():
    """Leads review page -- stub, Plan 02 replaces body."""
    return 'Coming soon', 200
