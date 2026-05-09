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
        if not admin_password:
            # Fail closed — never allow access when ADMIN_PASSWORD is unconfigured.
            # An empty password would allow any Basic-auth header with an empty
            # password field to pass the check below, silently opening every admin
            # endpoint to unauthenticated access.
            return Response(
                'Server misconfiguration: ADMIN_PASSWORD is not set',
                500,
                {'WWW-Authenticate': 'Basic realm="DocChat Admin"'}
            )
        auth = request.authorization
        if not auth or auth.password != admin_password:
            return Response(
                'Authentication required',
                401,
                {'WWW-Authenticate': 'Basic realm="DocChat Admin"'}
            )
        return f(*args, **kwargs)
    return decorated
