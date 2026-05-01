from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import face_labels, faces, people, photo_tags, photos


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
