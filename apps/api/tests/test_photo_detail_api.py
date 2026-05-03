from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import (
    face_labels,
    faces,
    people,
    photo_exif_attributes,
    photo_files,
    photo_tags,
    photos,
    storage_source_aliases,
    storage_sources,
    watched_folders,
)


def test_photo_detail_api_returns_projected_metadata_and_related_fields(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photo-detail-api.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 30, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                sha256="sha-1",
                phash="phash-1",
                shot_ts=now,
                shot_ts_source="exif:DateTimeOriginal",
                camera_make="Apple",
                camera_model="iPhone 15 Pro",
                software="18.1",
                orientation="Rotate 90 CW",
                gps_latitude=12.3456,
                gps_longitude=-45.6789,
                gps_altitude=123.4,
                created_ts=now,
                updated_ts=now,
                path="/photos/photo-1.jpg",
                filesize=1024,
                ext="jpg",
                modified_ts=now,
                faces_count=1,
                faces_detected_ts=now,
            )
        )
        connection.execute(insert(photo_tags).values(photo_id="photo-1", tag="vacation"))
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id="person-1",
                bbox_x=10,
                bbox_y=20,
                bbox_w=30,
                bbox_h=40,
            )
        )

    client = TestClient(app)
    response = client.get("/api/v1/photos/photo-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["photo_id"] == "photo-1"
    assert payload["path"] == "/photos/photo-1.jpg"
    assert payload["shot_ts"] == "2026-03-28T19:30:00Z"
    assert payload["tags"] == ["vacation"]
    assert payload["people"] == ["person-1"]
    assert payload["faces"] == [
        {
            "face_id": "face-1",
            "person_id": "person-1",
            "bbox_x": 10,
            "bbox_y": 20,
            "bbox_w": 30,
            "bbox_h": 40,
            "bbox_space_width": None,
            "bbox_space_height": None,
            "label_source": None,
            "confidence": None,
            "model_version": None,
            "provenance": None,
            "label_recorded_ts": None,
        }
    ]
    assert payload["thumbnail"] is None
    assert payload["original"] is None
    assert payload["metadata"]["camera_model"] == "iPhone 15 Pro"
    assert payload["metadata"]["software"] == "18.1"
    assert payload["metadata"]["gps_latitude"] == 12.3456
    assert payload["metadata"]["faces_count"] == 1


def test_photo_detail_api_returns_404_for_missing_photo(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photo-detail-api-missing.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    client = TestClient(app)
    response = client.get("/api/v1/photos/missing-photo")

    assert response.status_code == 404
    assert response.json()["detail"] == "Photo not found"


def test_photo_detail_api_exposes_bbox_coordinate_space_dimensions(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photo-detail-api-bbox-space.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 30, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                sha256="sha-1",
                created_ts=now,
                updated_ts=now,
                path="/photos/photo-1.jpg",
                filesize=1024,
                ext="jpg",
                faces_count=1,
            )
        )
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id=None,
                bbox_x=1000,
                bbox_y=300,
                bbox_w=800,
                bbox_h=600,
                provenance={
                    "bbox_space_width": 4000,
                    "bbox_space_height": 3000,
                },
            )
        )

    client = TestClient(app)
    response = client.get("/api/v1/photos/photo-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["faces"][0]["bbox_space_width"] == 4000
    assert payload["faces"][0]["bbox_space_height"] == 3000


def test_photo_detail_api_allows_missing_shot_timestamp(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photo-detail-api-null-shot-ts.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 30, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                sha256="sha-1",
                phash="phash-1",
                shot_ts=None,
                shot_ts_source=None,
                camera_make="Apple",
                camera_model="iPhone 15 Pro",
                software="18.1",
                orientation="Rotate 90 CW",
                created_ts=now,
                updated_ts=now,
                path="/photos/photo-1.jpg",
                filesize=1024,
                ext="jpg",
                modified_ts=now,
                faces_count=0,
                faces_detected_ts=None,
            )
        )

    client = TestClient(app)
    response = client.get("/api/v1/photos/photo-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["photo_id"] == "photo-1"
    assert payload["shot_ts"] is None
    assert payload["faces"] == []


def test_photo_detail_api_normalizes_legacy_shot_ts_source_using_exif_attributes(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photo-detail-api-shot-source-normalization.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 30, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                sha256="sha-1",
                shot_ts=now,
                shot_ts_source="exif:DateTimeOriginal",
                created_ts=now,
                updated_ts=now,
                path="/photos/photo-1.jpg",
                filesize=1024,
                ext="jpg",
                faces_count=0,
            )
        )
        connection.execute(
            insert(photo_exif_attributes).values(
                photo_id="photo-1",
                exif_attribute_name="exif_ifd.DateTimeOriginal",
                exif_attribute_value="2026:03:28 19:30:00",
            )
        )

    client = TestClient(app)
    response = client.get("/api/v1/photos/photo-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["shot_ts_source"] == "exif_ifd:DateTimeOriginal"


def test_photo_detail_api_returns_latest_matching_face_label_provenance(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photo-detail-api-provenance.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 30, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                sha256="sha-1",
                phash="phash-1",
                shot_ts=now,
                shot_ts_source="exif:DateTimeOriginal",
                camera_make="Apple",
                camera_model="iPhone 15 Pro",
                software="18.1",
                orientation="Rotate 90 CW",
                created_ts=now,
                updated_ts=now,
                path="/photos/photo-1.jpg",
                filesize=1024,
                ext="jpg",
                modified_ts=now,
                faces_count=1,
                faces_detected_ts=now,
            )
        )
        connection.execute(
            insert(people).values(
                person_id="person-1",
                display_name="Inez",
                created_ts=now,
                updated_ts=now,
            )
        )
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id="person-1",
                bbox_x=10,
                bbox_y=20,
                bbox_w=30,
                bbox_h=40,
            )
        )
        connection.execute(
            insert(face_labels).values(
                face_label_id="face-label-1",
                face_id="face-1",
                person_id="person-1",
                label_source="machine_applied",
                confidence=0.71,
                model_version="recognizer-v1",
                provenance={
                    "workflow": "recognition-suggestions",
                    "surface": "api",
                    "action": "auto_apply",
                },
                created_ts=datetime(2026, 3, 28, 19, 30, tzinfo=UTC),
                updated_ts=datetime(2026, 3, 28, 19, 31, tzinfo=UTC),
            )
        )
        connection.execute(
            insert(face_labels).values(
                face_label_id="face-label-2",
                face_id="face-1",
                person_id="person-1",
                label_source="human_confirmed",
                confidence=None,
                model_version=None,
                provenance={
                    "workflow": "face-labeling",
                    "surface": "api",
                    "action": "correction",
                },
                created_ts=datetime(2026, 3, 28, 19, 32, tzinfo=UTC),
                updated_ts=datetime(2026, 3, 28, 19, 33, tzinfo=UTC),
            )
        )

    client = TestClient(app)
    response = client.get("/api/v1/photos/photo-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["faces"] == [
        {
            "face_id": "face-1",
            "person_id": "person-1",
            "bbox_x": 10,
            "bbox_y": 20,
            "bbox_w": 30,
            "bbox_h": 40,
            "bbox_space_width": None,
            "bbox_space_height": None,
            "label_source": "human_confirmed",
            "confidence": None,
            "model_version": None,
            "provenance": {
                "workflow": "face-labeling",
                "surface": "api",
                "action": "correction",
            },
            "label_recorded_ts": "2026-03-28T19:33:00Z",
        }
    ]


def test_photo_original_api_streams_registered_source_file(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photo-original-api.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    source_root = tmp_path / "family-share"
    watched_root = source_root / "trips"
    watched_root.mkdir(parents=True)
    photo_bytes = b"not-a-real-jpeg-but-good-enough-for-stream-test"
    (watched_root / "photo-1.jpg").write_bytes(photo_bytes)
    (source_root / ".photo-org-source.json").write_text(
        json.dumps({"storage_source_id": "source-1", "marker_version": 1})
    )

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 30, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                sha256="sha-1",
                created_ts=now,
                updated_ts=now,
                path="/storage-sources/source-1/trips/photo-1.jpg",
                filesize=len(photo_bytes),
                ext="jpg",
                faces_count=0,
            )
        )
        connection.execute(
            insert(storage_sources).values(
                storage_source_id="source-1",
                display_name="Family share",
                marker_filename=".photo-org-source.json",
                marker_version=1,
                availability_state="active",
                last_failure_reason=None,
                last_validated_ts=now,
                created_ts=now,
                updated_ts=now,
            )
        )
        connection.execute(
            insert(storage_source_aliases).values(
                storage_source_alias_id="alias-1",
                storage_source_id="source-1",
                alias_path=str(source_root),
                created_ts=now,
                updated_ts=now,
            )
        )
        connection.execute(
            insert(watched_folders).values(
                watched_folder_id="wf-1",
                scan_path=str(watched_root),
                storage_source_id="source-1",
                relative_path="trips",
                display_name="Trips",
                is_enabled=1,
                availability_state="active",
                last_failure_reason=None,
                last_successful_scan_ts=now,
                created_ts=now,
                updated_ts=now,
            )
        )
        connection.execute(
            insert(photo_files).values(
                photo_file_id="pf-1",
                photo_id="photo-1",
                watched_folder_id="wf-1",
                relative_path="photo-1.jpg",
                filename="photo-1.jpg",
                extension="jpg",
                filesize=len(photo_bytes),
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

    client = TestClient(app)
    response = client.get("/api/v1/photos/photo-1/original")

    assert response.status_code == 200
    assert response.content == photo_bytes
    assert response.headers["content-type"].startswith("image/jpeg")


def test_photo_original_api_returns_404_when_file_is_unavailable(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photo-original-api-missing.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 19, 30, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                sha256="sha-1",
                created_ts=now,
                updated_ts=now,
                path="/storage-sources/source-1/trips/photo-1.jpg",
                filesize=1024,
                ext="jpg",
                faces_count=0,
            )
        )

    client = TestClient(app)
    response = client.get("/api/v1/photos/photo-1/original")

    assert response.status_code == 404
    assert response.json()["detail"] == "Original photo not found"
