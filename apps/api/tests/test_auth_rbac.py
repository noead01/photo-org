from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import faces, people, photos, users


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


def test_cloudflare_access_user_without_role_cannot_confirm_face(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'auth-rbac-face.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PHOTO_ORG_AUTH_MODE", "cloudflare_access")
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                sha256="sha256-photo-1",
                created_ts=now,
                updated_ts=now,
            )
        )
        connection.execute(
            insert(people).values(
                person_id="person-1",
                display_name="Jane Doe",
                created_ts=now,
                updated_ts=now,
            )
        )
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id=None,
            )
        )

    client = TestClient(app)
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "person-1"},
        headers={"Cf-Access-Authenticated-User-Email": "viewer@example.com"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Face validation role required"}
