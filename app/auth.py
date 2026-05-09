import os
import functools
from flask import request, Response


def require_auth(f):
    """HTTP Basic Auth stub. Checks password against ADMIN_PASSWORD env var.

    Phase 4 replaces this stub with full implementation (rate limiting,
    session tokens, etc.). For Phase 2, this protects admin endpoints
    against casual access while keeping the implementation minimal.

    Username is ignored — only the password is checked against ADMIN_PASSWORD.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        admin_password = os.environ.get('ADMIN_PASSWORD', '')
        auth = request.authorization
        if not auth or auth.password != admin_password:
            return Response(
                'Authentication required',
                401,
                {'WWW-Authenticate': 'Basic realm="DocChat Admin"'}
            )
        return f(*args, **kwargs)
    return decorated
