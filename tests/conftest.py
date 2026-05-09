import os
import pytest

@pytest.fixture(scope="function")  # WR-06: explicit scope — must stay function to isolate DB per test
def app(tmp_path, monkeypatch):
    """Flask test app with isolated storage and injected env vars.
    Does NOT require a real .env file — injects required env vars directly.
    """
    monkeypatch.setenv('SECRET_KEY', 'test-secret-key-do-not-use-in-prod')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-key')
    monkeypatch.setenv('ADMIN_PASSWORD', 'test-password')

    # Override STORAGE_PATH to a temp directory so tests don't touch ~/dochat/storage
    # We patch os.path.expanduser inside the app package so create_app() uses tmp_path
    import app as app_module
    original_expanduser = os.path.expanduser
    monkeypatch.setattr(
        app_module.os.path,
        'expanduser',
        lambda path: str(tmp_path / 'storage') if '~/dochat/storage' in path else original_expanduser(path)
    )

    from app import create_app
    flask_app = create_app()
    flask_app.config['TESTING'] = True

    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()
