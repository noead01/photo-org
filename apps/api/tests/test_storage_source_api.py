from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import ingest_runs, photo_files, photos


def test_storage_source_registration_api_creates_source_and_marker(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'storage-source-registration-api.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    root = tmp_path / "family-share"
    root.mkdir()

    client = TestClient(app)
    response = client.post(
        "/api/v1/storage-sources",
        json={
            "root_path": str(root),
            "alias_path": "//nas/family-share",
            "display_name": "Family Share",
        },
    )

    assert response.status_code == 201
    assert response.json()["display_name"] == "Family Share"
    assert response.json()["marker_filename"] == ".photo-org-source.json"
    assert response.json()["marker_version"] == 1
    assert (root / ".photo-org-source.json").is_file()


def test_storage_source_registration_api_reuses_existing_marker_identity(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'storage-source-registration-api-reuse.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    root = tmp_path / "family-share"
    root.mkdir()

    client = TestClient(app)
    first = client.post(
        "/api/v1/storage-sources",
        json={
            "root_path": str(root),
            "alias_path": "//nas/family-share",
            "display_name": "Family Share",
        },
    )
    second = client.post(
        "/api/v1/storage-sources",
        json={
            "root_path": str(root),
            "alias_path": "smb://family.local/family-share",
            "display_name": "Ignored Alias Name",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["storage_source_id"] == first.json()["storage_source_id"]
    assert second.json()["display_name"] == "Family Share"


def test_storage_source_registration_api_normalizes_alias_for_later_watched_folder_requests(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'storage-source-registration-api-normalized-alias.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    root = tmp_path / "family-share"
    root.mkdir()

    client = TestClient(app)
    registered = client.post(
        "/api/v1/storage-sources",
        json={
            "root_path": str(root),
            "alias_path": "\\\\nas\\family\\",
            "display_name": "Family Share",
        },
    )

    assert registered.status_code == 201

    created = client.post(
        f"/api/v1/storage-sources/{registered.json()['storage_source_id']}/watched-folders",
        json={
            "alias_path": "//nas/family",
            "watched_path": "//nas/family/2024/trips",
            "display_name": "Trips",
        },
    )

    assert created.status_code == 201
    assert created.json()["relative_path"] == "2024/trips"


def test_storage_source_registration_api_rejects_invalid_root(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'storage-source-registration-api-invalid-root.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    client = TestClient(app)
    missing_root = tmp_path / "missing-share"
    response = client.post(
        "/api/v1/storage-sources",
        json={
            "root_path": str(missing_root),
            "alias_path": "//nas/missing-share",
            "display_name": "Missing Share",
        },
    )

    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_storage_source_registration_api_rejects_malformed_marker_file(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'storage-source-registration-api-bad-marker.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    root = tmp_path / "family-share"
    root.mkdir()
    (root / ".photo-org-source.json").write_text("{not-json")

    client = TestClient(app)
    response = client.post(
        "/api/v1/storage-sources",
        json={
            "root_path": str(root),
            "alias_path": "//nas/family-share",
            "display_name": "Family Share",
        },
    )

    assert response.status_code == 400
    assert "marker" in response.json()["detail"]


def test_storage_source_registration_api_rejects_marker_missing_storage_source_id(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'storage-source-registration-api-missing-marker-key.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    root = tmp_path / "family-share"
    root.mkdir()
    (root / ".photo-org-source.json").write_text(json.dumps({"marker_version": 1}))

    client = TestClient(app)
    response = client.post(
        "/api/v1/storage-sources",
        json={
            "root_path": str(root),
            "alias_path": "//nas/family-share",
            "display_name": "Family Share",
        },
    )

    assert response.status_code == 400
    assert "marker" in response.json()["detail"]


def test_storage_source_registration_api_rejects_empty_root_path(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'storage-source-registration-api-empty-root.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    client = TestClient(app)
    response = client.post(
        "/api/v1/storage-sources",
        json={
            "root_path": "   ",
            "alias_path": "//nas/family-share",
            "display_name": "Family Share",
        },
    )

    assert response.status_code == 422
    assert any(error["loc"][-1] == "root_path" for error in response.json()["detail"])


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


def test_storage_source_watched_folder_mutations_enforce_source_ownership(tmp_path, monkeypatch):
    from app.services.storage_sources import (
        attach_storage_source_alias,
        create_storage_source,
    )

    database_url = f"sqlite:///{tmp_path / 'storage-source-api-ownership.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 40, tzinfo=UTC)
    with engine.begin() as connection:
        source_a = create_storage_source(
            connection,
            display_name="Family NAS",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        source_b = create_storage_source(
            connection,
            display_name="Travel NAS",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source_a["storage_source_id"],
            alias_path="//nas/family",
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source_b["storage_source_id"],
            alias_path="//nas/travel",
            now=now,
        )

    client = TestClient(app)
    created = client.post(
        f"/api/v1/storage-sources/{source_b['storage_source_id']}/watched-folders",
        json={
            "alias_path": "//nas/travel",
            "watched_path": "//nas/travel/2024/trips",
            "display_name": "Trips",
        },
    )
    watched_folder_id = created.json()["watched_folder_id"]

    wrong_patch = client.patch(
        f"/api/v1/storage-sources/{source_a['storage_source_id']}/watched-folders/{watched_folder_id}",
        json={"is_enabled": False},
    )
    assert wrong_patch.status_code == 404

    wrong_delete = client.delete(
        f"/api/v1/storage-sources/{source_a['storage_source_id']}/watched-folders/{watched_folder_id}"
    )
    assert wrong_delete.status_code == 404


def test_storage_sources_api_lists_source_health_latest_runs_and_catalog_availability(
    tmp_path, monkeypatch
):
    from app.services.storage_sources import (
        attach_storage_source_alias,
        create_storage_source,
        update_storage_source_availability,
    )
    from app.services.watched_folders import create_watched_folder

    database_url = f"sqlite:///{tmp_path / 'storage-source-api-status.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    root = tmp_path / "family-share"
    watched_root = root / "2024" / "trips"
    watched_root.mkdir(parents=True)
    now = datetime(2026, 3, 29, 14, 0, tzinfo=UTC)

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family Share",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=str(root),
            now=now,
        )
        watched_folder = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=str(root),
            watched_path=str(watched_root),
            display_name="Trips",
            now=now,
        )
        update_storage_source_availability(
            connection,
            storage_source_id=source["storage_source_id"],
            availability_state="unreachable",
            last_failure_reason="folder_unmounted",
            now=now,
        )
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                path=f"/storage-sources/{source['storage_source_id']}/2024/trips/arrival.jpg",
                sha256="a" * 64,
                phash=None,
                filesize=123,
                ext="jpg",
                created_ts=now,
                modified_ts=now,
                shot_ts=now,
                shot_ts_source="exif:DateTime",
                camera_make="Canon",
                camera_model="EOS",
                software=None,
                orientation="landscape",
                gps_latitude=None,
                gps_longitude=None,
                gps_altitude=None,
                thumbnail_jpeg=b"thumb",
                thumbnail_mime_type="image/jpeg",
                thumbnail_width=64,
                thumbnail_height=48,
                updated_ts=now,
                deleted_ts=None,
                faces_count=0,
                faces_detected_ts=None,
            )
        )
        connection.execute(
            insert(photo_files).values(
                photo_file_id="photo-file-1",
                photo_id="photo-1",
                watched_folder_id=watched_folder["watched_folder_id"],
                relative_path="arrival.jpg",
                filename="arrival.jpg",
                extension="jpg",
                filesize=123,
                created_ts=now,
                modified_ts=now,
                first_seen_ts=now,
                last_seen_ts=now,
                missing_ts=None,
                deleted_ts=None,
                lifecycle_state="active",
                absence_reason=None,
            )
        )
        connection.execute(
            insert(ingest_runs).values(
                ingest_run_id="run-failed",
                watched_folder_id=watched_folder["watched_folder_id"],
                status="failed",
                started_ts=now,
                completed_ts=now,
                files_seen=0,
                files_created=0,
                files_updated=0,
                files_missing=0,
                error_count=1,
                error_summary="marker mismatch on alias //nas/family-share",
            )
        )
        connection.execute(
            insert(ingest_runs).values(
                ingest_run_id="run-ok",
                watched_folder_id=watched_folder["watched_folder_id"],
                status="completed",
                started_ts=now.replace(hour=13),
                completed_ts=now.replace(hour=13),
                files_seen=10,
                files_created=2,
                files_updated=1,
                files_missing=0,
                error_count=0,
                error_summary=None,
            )
        )

    client = TestClient(app)

    response = client.get("/api/v1/storage-sources")

    assert response.status_code == 200
    assert len(response.json()) == 1
    payload = response.json()[0]
    assert payload["storage_source_id"] == source["storage_source_id"]
    assert payload["availability_state"] == "unreachable"
    assert payload["last_failure_reason"] == "folder_unmounted"
    assert payload["watched_folder_count"] == 1
    assert payload["unreachable_watched_folder_count"] == 0
    assert payload["catalog"]["metadata_queryable"] is True
    assert payload["catalog"]["thumbnails_available"] is True
    assert payload["catalog"]["originals_available"] is False
    assert payload["latest_ingest_run"]["status"] == "failed"
    assert payload["latest_ingest_run"]["error_summary"] == "marker mismatch on alias //nas/family-share"
    assert payload["recent_failures"] == [
        {
            "watched_folder_id": watched_folder["watched_folder_id"],
            "status": "failed",
            "error_summary": "marker mismatch on alias //nas/family-share",
            "completed_ts": "2026-03-29T14:00:00Z",
        }
    ]


def test_storage_source_detail_api_includes_ingest_status_summary(tmp_path, monkeypatch):
    from app.services.storage_sources import (
        attach_storage_source_alias,
        create_storage_source,
        update_storage_source_availability,
    )
    from app.services.watched_folders import create_watched_folder

    database_url = f"sqlite:///{tmp_path / 'storage-source-api-detail.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    root = tmp_path / "family-share"
    watched_root = root / "2024" / "trips"
    watched_root.mkdir(parents=True)
    now = datetime(2026, 3, 29, 14, 0, tzinfo=UTC)

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family Share",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=str(root),
            now=now,
        )
        watched_folder = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=str(root),
            watched_path=str(watched_root),
            display_name="Trips",
            now=now,
        )
        update_storage_source_availability(
            connection,
            storage_source_id=source["storage_source_id"],
            availability_state="unreachable",
            last_failure_reason="folder_unmounted",
            now=now,
        )
        connection.execute(
            insert(ingest_runs).values(
                ingest_run_id="run-failed",
                watched_folder_id=watched_folder["watched_folder_id"],
                status="failed",
                started_ts=now,
                completed_ts=now,
                files_seen=0,
                files_created=0,
                files_updated=0,
                files_missing=0,
                error_count=1,
                error_summary="marker mismatch on alias //nas/family-share",
            )
        )

    client = TestClient(app)

    response = client.get(f"/api/v1/storage-sources/{source['storage_source_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["storage_source_id"] == source["storage_source_id"]
    assert payload["availability_state"] == "unreachable"
    assert payload["watched_folder_count"] == 1
    assert payload["unreachable_watched_folder_count"] == 0
    assert payload["catalog"]["metadata_queryable"] is False
    assert payload["catalog"]["thumbnails_available"] is False
    assert payload["catalog"]["originals_available"] is False
    assert payload["latest_ingest_run"]["status"] == "failed"
    assert payload["recent_failures"] == [
        {
            "watched_folder_id": watched_folder["watched_folder_id"],
            "status": "failed",
            "error_summary": "marker mismatch on alias //nas/family-share",
            "completed_ts": "2026-03-29T14:00:00Z",
        }
    ]


def test_storage_source_detail_api_returns_404_for_missing_source(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'storage-source-api-detail-missing.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    client = TestClient(app)

    response = client.get("/api/v1/storage-sources/missing-source-id")

    assert response.status_code == 404


def test_storage_source_watched_folder_list_includes_latest_ingest_run_summary(tmp_path, monkeypatch):
    from app.services.storage_sources import (
        attach_storage_source_alias,
        create_storage_source,
    )
    from app.services.watched_folders import create_watched_folder

    database_url = f"sqlite:///{tmp_path / 'storage-source-api-watched-folder-status.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    root = tmp_path / "family-share"
    watched_root = root / "2024" / "trips"
    watched_root.mkdir(parents=True)
    now = datetime(2026, 3, 29, 15, 0, tzinfo=UTC)

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        source = create_storage_source(
            connection,
            display_name="Family Share",
            marker_filename=".photo-org-source.json",
            marker_version=1,
            now=now,
        )
        attach_storage_source_alias(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=str(root),
            now=now,
        )
        watched_folder = create_watched_folder(
            connection,
            storage_source_id=source["storage_source_id"],
            alias_path=str(root),
            watched_path=str(watched_root),
            display_name="Trips",
            now=now,
        )
        connection.execute(
            insert(ingest_runs).values(
                ingest_run_id="run-1",
                watched_folder_id=watched_folder["watched_folder_id"],
                status="completed",
                started_ts=now.replace(hour=14),
                completed_ts=now.replace(hour=14),
                files_seen=12,
                files_created=3,
                files_updated=2,
                files_missing=1,
                error_count=0,
                error_summary=None,
            )
        )

    client = TestClient(app)

    response = client.get(
        f"/api/v1/storage-sources/{source['storage_source_id']}/watched-folders"
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "watched_folder_id": watched_folder["watched_folder_id"],
            "storage_source_id": source["storage_source_id"],
            "scan_path": str(watched_root),
            "relative_path": "2024/trips",
            "display_name": "Trips",
            "is_enabled": 1,
            "availability_state": "active",
            "last_failure_reason": None,
            "last_successful_scan_ts": None,
            "latest_ingest_run": {
                "status": "completed",
                "files_seen": 12,
                "files_created": 3,
                "files_updated": 2,
                "files_missing": 1,
                "error_count": 0,
                "error_summary": None,
                "completed_ts": "2026-03-29T14:00:00Z",
            },
        }
    ]
