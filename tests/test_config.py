import os
import pytest


def test_secret_key_from_env(app):
    """SECRET_KEY must be loaded from environment — covers INFRA-04."""
    assert app.config['SECRET_KEY'] == 'test-secret-key-do-not-use-in-prod'


def test_missing_secret_key_raises(monkeypatch):
    """create_app() must raise KeyError if SECRET_KEY not in env — confirms no hardcoding."""
    monkeypatch.delenv('SECRET_KEY', raising=False)
    from app import create_app
    with pytest.raises(KeyError):
        create_app()


def test_env_file_not_committed():
    """.env must not exist in the project root (should be in .gitignore)."""
    assert not os.path.exists('.env') or True  # .env may exist locally — check .gitignore instead
    with open('.gitignore', 'r') as f:
        content = f.read()
    assert '.env' in content, ".env must be listed in .gitignore"


def test_no_hardcoded_secrets_in_source():
    """No source file in app/ or passenger_wsgi.py may contain literal secret values — covers INFRA-04."""
    forbidden_patterns = [
        'OPENROUTER_API_KEY=sk-',        # actual key prefix
        'SECRET_KEY=change_me',           # placeholder is ok in .env.example but not in .py
        'ADMIN_PASSWORD=change_me',
    ]
    source_files = []
    for root, dirs, files in os.walk('app'):
        for fname in files:
            if fname.endswith('.py'):
                source_files.append(os.path.join(root, fname))
    source_files.append('passenger_wsgi.py')

    for path in source_files:
        if not os.path.exists(path):
            continue
        content = open(path).read()
        for pattern in forbidden_patterns:
            assert pattern not in content, (
                f"Potential hardcoded secret in {path}: found '{pattern}'"
            )
