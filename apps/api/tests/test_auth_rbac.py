from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import faces, people, photos, user_role_assignments, users


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


def test_cloudflare_access_session_endpoint_returns_roles_and_capabilities(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'auth-rbac-session.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PHOTO_ORG_AUTH_MODE", "cloudflare_access")
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
        connection.execute(
            insert(users).values(
                user_id="admin-user",
                auth_provider="cloudflare_access",
                auth_subject="admin@example.com",
                email="admin@example.com",
                display_name="Admin User",
                created_ts=now,
                updated_ts=now,
            )
        )
        connection.execute(
            insert(user_role_assignments).values(
                user_id="admin-user",
                role="admin",
                created_ts=now,
                updated_ts=now,
            )
        )

    client = TestClient(app)
    response = client.get(
        "/api/v1/admin/session",
        headers={"Cf-Access-Authenticated-User-Email": "admin@example.com"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "admin-user",
        "email": "admin@example.com",
        "display_name": "Admin User",
        "roles": ["admin"],
        "capabilities": {
            "add_to_album": True,
            "export": True,
            "review_faces": True,
            "manage_roles": True,
            "manage_sources": True,
        },
    }


def test_cloudflare_access_admin_can_list_and_replace_user_roles(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'auth-rbac-admin.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PHOTO_ORG_AUTH_MODE", "cloudflare_access")
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
        connection.execute(
            insert(users).values(
                [
                    {
                        "user_id": "admin-user",
                        "auth_provider": "cloudflare_access",
                        "auth_subject": "admin@example.com",
                        "email": "admin@example.com",
                        "display_name": "Admin User",
                        "created_ts": now,
                        "updated_ts": now,
                    },
                    {
                        "user_id": "viewer-user",
                        "auth_provider": "cloudflare_access",
                        "auth_subject": "viewer@example.com",
                        "email": "viewer@example.com",
                        "display_name": None,
                        "created_ts": now,
                        "updated_ts": now,
                    },
                ]
            )
        )
        connection.execute(
            insert(user_role_assignments).values(
                user_id="admin-user",
                role="admin",
                created_ts=now,
                updated_ts=now,
            )
        )

    client = TestClient(app)

    list_response = client.get(
        "/api/v1/admin/users",
        headers={"Cf-Access-Authenticated-User-Email": "admin@example.com"},
    )

    assert list_response.status_code == 200
    assert [row["user_id"] for row in list_response.json()] == ["admin-user", "viewer-user"]
    assert list_response.json()[1]["roles"] == []

    update_response = client.put(
        "/api/v1/admin/users/viewer-user/roles",
        json={"roles": ["viewer", "contributor"]},
        headers={"Cf-Access-Authenticated-User-Email": "admin@example.com"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["roles"] == ["viewer", "contributor"]

    with engine.connect() as connection:
        roles = connection.execute(
            select(user_role_assignments.c.role).where(
                user_role_assignments.c.user_id == "viewer-user"
            )
        ).scalars().all()
    assert roles == ["contributor", "viewer"] or roles == ["viewer", "contributor"]


def test_cloudflare_access_non_admin_cannot_manage_roles(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'auth-rbac-non-admin.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PHOTO_ORG_AUTH_MODE", "cloudflare_access")
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
        connection.execute(
            insert(users).values(
                user_id="contributor-user",
                auth_provider="cloudflare_access",
                auth_subject="contributor@example.com",
                email="contributor@example.com",
                display_name=None,
                created_ts=now,
                updated_ts=now,
            )
        )
        connection.execute(
            insert(user_role_assignments).values(
                user_id="contributor-user",
                role="contributor",
                created_ts=now,
                updated_ts=now,
            )
        )

    client = TestClient(app)
    response = client.get(
        "/api/v1/admin/users",
        headers={"Cf-Access-Authenticated-User-Email": "contributor@example.com"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin role required"}
