import os
from flask import Flask
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

    return app
