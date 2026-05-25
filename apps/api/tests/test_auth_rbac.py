from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import users


def test_cloudflare_access_auto_provisions_user_without_roles(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'auth-rbac.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PHOTO_ORG_AUTH_MODE", "cloudflare_access")
    _get_session_factory.cache_clear()

    client = TestClient(app)
    response = client.get(
        "/api/v1/albums",
        headers={"Cf-Access-Authenticated-User-Email": "new.user@example.com"},
    )

    assert response.status_code == 200
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        persisted = connection.execute(
            select(users.c.email, users.c.auth_provider)
        ).mappings().all()
    assert persisted == [{"email": "new.user@example.com", "auth_provider": "cloudflare_access"}]
