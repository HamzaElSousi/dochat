from flask import Blueprint
from ..auth import require_auth

admin_api_bp = Blueprint('admin_api', __name__)
