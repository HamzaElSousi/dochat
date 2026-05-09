import os
from flask import Flask
from .db import init_db
from .routes.health import health_bp
from .routes.ingest import ingest_bp


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    # os.path.expanduser is required — Python does not auto-expand ~ in strings.
    app.config['STORAGE_PATH'] = os.path.expanduser('~/dochat/storage')

    init_db(app)

    app.register_blueprint(health_bp)
    app.register_blueprint(ingest_bp)

    return app
