from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy import create_engine, insert, select

from app.migrations import upgrade_database
from app.storage import faces, photos

pytest.importorskip("PIL")
from PIL import Image


def _write_test_image(path: Path) -> None:
    image = Image.new("RGB", (2, 2), color=(255, 0, 0))
    image.save(path, format="JPEG")


def _photo_row_values(
    *,
    photo_id: str,
    path: str,
    sha256: str,
    now: datetime,
    thumbnail_jpeg: bytes | None,
    thumbnail_mime_type: str | None,
    thumbnail_width: int | None,
    thumbnail_height: int | None,
    faces_count: int,
    faces_detected_ts: datetime | None,
) -> dict[str, object]:
    return {
        "photo_id": photo_id,
        "path": path,
        "sha256": sha256,
        "phash": None,
        "filesize": 123,
        "ext": "jpg",
        "created_ts": now,
        "modified_ts": now,
        "shot_ts": None,
        "shot_ts_source": None,
        "camera_make": None,
        "camera_model": None,
        "software": None,
        "orientation": None,
        "gps_latitude": None,
        "gps_longitude": None,
        "gps_altitude": None,
        "thumbnail_jpeg": thumbnail_jpeg,
        "thumbnail_mime_type": thumbnail_mime_type,
        "thumbnail_width": thumbnail_width,
        "thumbnail_height": thumbnail_height,
        "updated_ts": now,
        "faces_count": faces_count,
        "faces_detected_ts": faces_detected_ts,
    }


def test_build_photo_record_captures_identity_and_metadata(tmp_path):
    from app.processing.ingest_persistence import build_photo_record

    photo_path = tmp_path / "photo.jpg"
    _write_test_image(photo_path)
    canonical_path = "/library/photo.jpg"

    record = build_photo_record(photo_path, canonical_path=canonical_path)

    assert record.path == canonical_path
    assert record.photo_id == str(
        uuid5(NAMESPACE_URL, f"{canonical_path}:{hashlib.sha256(photo_path.read_bytes()).hexdigest()}")
    )
    assert record.sha256 == hashlib.sha256(photo_path.read_bytes()).hexdigest()
    assert record.filesize == photo_path.stat().st_size
    assert record.ext == "jpg"
    assert record.created_ts is not None
    assert record.modified_ts is not None
    assert record.faces_count == 0


def test_build_ingest_submission_serializes_photo_record_fields(tmp_path):
    from app.processing.ingest_persistence import build_ingest_submission, build_photo_record

    photo_path = tmp_path / "photo.jpg"
    _write_test_image(photo_path)

    expected_record = build_photo_record(photo_path, canonical_path="/library/photo.jpg")
    payload = build_ingest_submission(
        photo_path,
        scan_root=tmp_path,
        path_root="/library",
    )

    assert payload["photo_id"] == expected_record.photo_id
    assert payload["path"] == expected_record.path
    assert payload["sha256"] == expected_record.sha256
    assert payload["created_ts"] == expected_record.created_ts.isoformat()
    assert payload["modified_ts"] == expected_record.modified_ts.isoformat()
    assert payload["shot_ts"] is None
    assert payload["faces_count"] == 0
    assert payload["idempotency_key"] == expected_record.photo_id


def test_upsert_photo_preserves_existing_thumbnail_when_new_record_lacks_one(tmp_path):
    from app.processing.ingest_persistence import PhotoRecord, upsert_photo

    database_url = f"sqlite:///{tmp_path / 'upsert-photo.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 20, 0, tzinfo=UTC)
    path = "/library/photo.jpg"

    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                _photo_row_values(
                    photo_id="photo-1",
                    path=path,
                    sha256="a" * 64,
                    now=now,
                    thumbnail_jpeg=b"old-thumbnail",
                    thumbnail_mime_type="image/jpeg",
                    thumbnail_width=64,
                    thumbnail_height=48,
                    faces_count=3,
                    faces_detected_ts=now - timedelta(days=1),
                )
            )
        )
        created = upsert_photo(
            connection,
            PhotoRecord(
                photo_id="photo-1",
                path=path,
                sha256="b" * 64,
                filesize=124,
                ext="jpg",
                created_ts=now,
                modified_ts=now + timedelta(minutes=1),
                shot_ts=None,
                shot_ts_source=None,
                camera_make=None,
                camera_model=None,
                software=None,
                orientation=None,
                gps_latitude=None,
                gps_longitude=None,
                gps_altitude=None,
                thumbnail_jpeg=None,
                thumbnail_mime_type=None,
                thumbnail_width=None,
                thumbnail_height=None,
                faces_count=4,
            ),
        )
        row = connection.execute(
            select(
                photos.c.thumbnail_jpeg,
                photos.c.thumbnail_mime_type,
                photos.c.thumbnail_width,
                photos.c.thumbnail_height,
                photos.c.faces_count,
                photos.c.updated_ts,
            ).where(photos.c.path == path)
        ).mappings().one()

    assert created is False
    assert row["thumbnail_jpeg"] == b"old-thumbnail"
    assert row["thumbnail_mime_type"] == "image/jpeg"
    assert row["thumbnail_width"] == 64
    assert row["thumbnail_height"] == 48
    assert row["faces_count"] == 4
    assert row["updated_ts"] == now + timedelta(minutes=1)


def test_upsert_source_photo_reuses_existing_photo_id_and_detection_state(tmp_path):
    from app.processing.ingest_persistence import PhotoRecord, upsert_source_photo

    database_url = f"sqlite:///{tmp_path / 'upsert-source-photo.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 21, 0, tzinfo=UTC)
    detected_ts = now - timedelta(days=1)
    existing_path = "/storage-sources/source-1/imports/photo.jpg"
    moved_path = "/storage-sources/source-1/exports/photo.jpg"

    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                _photo_row_values(
                    photo_id="photo-1",
                    path=existing_path,
                    sha256="c" * 64,
                    now=now,
                    thumbnail_jpeg=b"old-thumbnail",
                    thumbnail_mime_type="image/jpeg",
                    thumbnail_width=64,
                    thumbnail_height=48,
                    faces_count=1,
                    faces_detected_ts=detected_ts,
                )
            )
        )
        created, photo_id = upsert_source_photo(
            connection,
            PhotoRecord(
                photo_id="photo-2",
                path=moved_path,
                sha256="c" * 64,
                filesize=124,
                ext="jpg",
                created_ts=now,
                modified_ts=now + timedelta(minutes=1),
                shot_ts=None,
                shot_ts_source=None,
                camera_make=None,
                camera_model=None,
                software=None,
                orientation=None,
                gps_latitude=None,
                gps_longitude=None,
                gps_altitude=None,
                thumbnail_jpeg=None,
                thumbnail_mime_type=None,
                thumbnail_width=None,
                thumbnail_height=None,
                faces_count=0,
            ),
        )
        row = connection.execute(
            select(
                photos.c.photo_id,
                photos.c.path,
                photos.c.thumbnail_jpeg,
                photos.c.faces_count,
                photos.c.faces_detected_ts,
            ).where(photos.c.photo_id == "photo-1")
        ).mappings().one()

    assert created is False
    assert photo_id == "photo-1"
    assert row["path"] == moved_path
    assert row["thumbnail_jpeg"] == b"old-thumbnail"
    assert row["faces_count"] == 1
    assert row["faces_detected_ts"] == detected_ts


def test_store_face_detections_replaces_existing_faces_and_updates_photo_counts(tmp_path):
    from app.processing.ingest_persistence import store_face_detections

    database_url = f"sqlite:///{tmp_path / 'store-faces.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 3, 28, 22, 0, tzinfo=UTC)
    photo_id = "photo-1"

    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                _photo_row_values(
                    photo_id=photo_id,
                    path="/library/photo.jpg",
                    sha256="d" * 64,
                    now=now,
                    thumbnail_jpeg=None,
                    thumbnail_mime_type=None,
                    thumbnail_width=None,
                    thumbnail_height=None,
                    faces_count=0,
                    faces_detected_ts=None,
                )
            )
        )
        connection.execute(
            insert(faces).values(
                face_id="old-face",
                photo_id=photo_id,
                person_id=None,
                bbox_x=None,
                bbox_y=None,
                bbox_w=None,
                bbox_h=None,
                bitmap=None,
                embedding=None,
                provenance={},
            )
        )
        store_face_detections(
            connection,
            photo_id,
            [
                {
                    "face_id": "face-1",
                    "person_id": "person-1",
                    "bbox_x": 1,
                    "bbox_y": 2,
                    "bbox_w": 3,
                    "bbox_h": 4,
                    "bitmap": b"bitmap",
                    "embedding": b"embedding",
                    "provenance": {"detector": "test"},
                }
            ],
        )
        face_rows = connection.execute(
            select(faces).where(faces.c.photo_id == photo_id)
        ).mappings().all()
        photo_row = connection.execute(
            select(photos.c.faces_count, photos.c.faces_detected_ts).where(
                photos.c.photo_id == photo_id
            )
        ).mappings().one()

    assert len(face_rows) == 1
    assert face_rows[0]["face_id"] == "face-1"
    assert face_rows[0]["provenance"] == {"detector": "test"}
    assert photo_row["faces_count"] == 1
    assert photo_row["faces_detected_ts"] is not None
