import os
from flask import Blueprint, jsonify, current_app

health_bp = Blueprint('health', __name__)


@health_bp.route('/health')
def health():
    mode = current_app.config.get('SQLITE_VEC_MODE', 'unknown')
    storage_path = current_app.config.get('STORAGE_PATH', '')

    # Verify storage is writable — write + delete a sentinel file
    storage_ok = False
    try:
        test_file = os.path.join(storage_path, '.write_test')
        with open(test_file, 'w') as f:
            f.write('ok')
        os.remove(test_file)
        storage_ok = True
    except OSError:
        storage_ok = False

    # Get sqlite_vec version via SQL function
    vec_version = 'unknown'
    try:
        conn = current_app.config.get('DB_CONN')
        if conn and mode == 'native':
            row = conn.execute("SELECT vec_version()").fetchone()
            vec_version = row[0] if row else 'unavailable'
    except Exception:
        # Never expose exception details — return generic string (V7 error handling)
        vec_version = 'unavailable'

    overall_ok = storage_ok and mode in ('native', 'python-fallback')
    response = {
        "status": "ok" if (storage_ok and mode == "native") else "degraded",
        "sqlite_vec_version": vec_version,
        "sqlite_vec_mode": mode,
        "storage_path": storage_path,
        "storage_writable": storage_ok,
    }

    if mode == "python-fallback":
        response["warning"] = "native extension unavailable — investigate SQLite version"

    status_code = 200 if overall_ok else 503
    return jsonify(response), status_code
