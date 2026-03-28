from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database


def test_storage_source_watched_folder_crud_api(tmp_path, monkeypatch):
    from app.services.storage_sources import (
        attach_storage_source_alias,
        create_storage_source,
    )

    database_url = f"sqlite:///{tmp_path / 'storage-source-api.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 30, tzinfo=UTC)
    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family NAS",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path="//nas/family",
            now=now,
        )

    client = TestClient(app)

    created = client.post(
        f"/api/v1/storage-sources/{source['storage_source_id']}/watched-folders",
        json={
            "alias_path": "//nas/family",
            "watched_path": "//nas/family/2024/trips",
            "display_name": "Trips",
        },
    )

    assert created.status_code == 201
    assert created.json()["relative_path"] == "2024/trips"
    assert created.json()["display_name"] == "Trips"
    watched_folder_id = created.json()["watched_folder_id"]

    listed = client.get(f"/api/v1/storage-sources/{source['storage_source_id']}/watched-folders")

    assert listed.status_code == 200
    assert [row["relative_path"] for row in listed.json()] == ["2024/trips"]

    disabled = client.patch(
        f"/api/v1/storage-sources/{source['storage_source_id']}/watched-folders/{watched_folder_id}",
        json={"is_enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_enabled"] == 0

    enabled = client.patch(
        f"/api/v1/storage-sources/{source['storage_source_id']}/watched-folders/{watched_folder_id}",
        json={"is_enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["is_enabled"] == 1

    deleted = client.delete(
        f"/api/v1/storage-sources/{source['storage_source_id']}/watched-folders/{watched_folder_id}"
    )
    assert deleted.status_code == 204

    after_delete = client.get(f"/api/v1/storage-sources/{source['storage_source_id']}/watched-folders")
    assert after_delete.status_code == 200
    assert after_delete.json() == []


def test_storage_source_watched_folder_create_rejects_outside_boundary(tmp_path, monkeypatch):
    from app.services.storage_sources import (
        attach_storage_source_alias,
        create_storage_source,
    )

    database_url = f"sqlite:///{tmp_path / 'storage-source-api-boundary.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 35, tzinfo=UTC)
    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family NAS",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path="//nas/family",
            now=now,
        )

    client = TestClient(app)
    response = client.post(
        f"/api/v1/storage-sources/{source['storage_source_id']}/watched-folders",
        json={
            "alias_path": "//nas/family",
            "watched_path": "//nas/other/trips",
            "display_name": "Trips",
        },
    )

    assert response.status_code == 400
    assert "outside source boundary" in response.json()["detail"]
