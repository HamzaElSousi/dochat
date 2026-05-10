import os
from flask import Flask, send_from_directory
from .db import init_db
from .routes.health import health_bp
from .routes.ingest import ingest_bp
from .routes.chat import chat_bp          # new — Plan 03 creates this file
from .routes.admin import admin_bp
from .routes.admin_api import admin_api_bp


def create_app():
    import os as _os
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    app = Flask(__name__,
                template_folder=_os.path.join(_root, 'templates'),
                static_folder=_os.path.join(_root, 'static'))

    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    # os.path.expanduser is required — Python does not auto-expand ~ in strings.
    app.config['STORAGE_PATH'] = os.path.expanduser('~/dochat/storage')

    init_db(app)

    app.register_blueprint(health_bp)
    app.register_blueprint(ingest_bp)
    app.register_blueprint(chat_bp)       # new — D-04
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_api_bp)

    @app.route('/dochat/widget.js')
    def widget_js():
        """Serve the embeddable chat widget JS file.

        URL: GET /dochat/widget.js
        Returns: widget.js with Content-Type: application/javascript
        Cache-Control: public, max-age=300 (5-minute cache — reasonable for widget updates)

        send_from_directory with explicit filename='widget.js' prevents path traversal —
        Flask validates the filename against the directory (T-05-11 mitigated).
        """
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        return send_from_directory(
            static_dir, 'widget.js',
            mimetype='application/javascript',
            max_age=300,
        )

    return app
