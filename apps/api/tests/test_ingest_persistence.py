from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

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


def _normalize_timestamp(value: datetime | None) -> datetime | None:
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _decode_base64_text(value: str | None) -> bytes | None:
    if value is None:
        return None
    return base64.b64decode(value)


def test_build_photo_record_returns_stable_identity_for_same_file_and_path(tmp_path):
    from app.processing.ingest_persistence import build_photo_record

    photo_path = tmp_path / "photo.jpg"
    _write_test_image(photo_path)
    canonical_path = "/library/photo.jpg"

    first = build_photo_record(photo_path, canonical_path=canonical_path)
    second = build_photo_record(photo_path, canonical_path=canonical_path)

    assert first.photo_id == second.photo_id
    assert first.path == canonical_path
    assert first.sha256 == hashlib.sha256(photo_path.read_bytes()).hexdigest()
    assert first.filesize == photo_path.stat().st_size
    assert first.ext == "jpg"
    assert first.created_ts is not None
    assert first.modified_ts is not None
    assert first.faces_count == 0


def test_build_photo_record_changes_identity_when_canonical_path_changes(tmp_path):
    from app.processing.ingest_persistence import build_photo_record

    photo_path = tmp_path / "photo.jpg"
    _write_test_image(photo_path)

    first = build_photo_record(photo_path, canonical_path="/library/photo.jpg")
    second = build_photo_record(photo_path, canonical_path="/archive/photo.jpg")

    assert first.photo_id != second.photo_id


def test_build_ingest_submission_serializes_expected_payload_fields(tmp_path):
    from app.processing.ingest_persistence import build_ingest_submission

    photo_path = tmp_path / "photo.jpg"
    _write_test_image(photo_path)

    payload = build_ingest_submission(
        photo_path,
        scan_root=tmp_path,
        path_root="/library",
    )

    assert payload["path"] == "/library/photo.jpg"
    assert payload["sha256"] == hashlib.sha256(photo_path.read_bytes()).hexdigest()
    assert len(payload["photo_id"]) > 0
    assert payload["idempotency_key"] == payload["photo_id"]
    assert payload["created_ts"].endswith("+00:00") or payload["created_ts"].endswith("Z")
    assert payload["modified_ts"].endswith("+00:00") or payload["modified_ts"].endswith("Z")
    assert payload["shot_ts"] is None
    assert payload["shot_ts_source"] is None
    assert payload["camera_make"] is None
    assert payload["camera_model"] is None
    assert payload["software"] is None
    assert payload["orientation"] is None
    assert payload["gps_latitude"] is None
    assert payload["gps_longitude"] is None
    assert payload["gps_altitude"] is None
    assert payload["faces_count"] == 0


def test_build_ingest_candidate_submission_serializes_discovery_only_fields(tmp_path):
    from app.processing.ingest_persistence import build_ingest_candidate_submission

    scan_root = tmp_path / "library"
    scan_root.mkdir()
    photo_path = scan_root / "sample.jpg"
    photo_path.write_bytes(b"candidate-bytes")

    payload = build_ingest_candidate_submission(
        photo_path,
        scan_root=scan_root,
        canonical_path="/library/sample.jpg",
        storage_source_id="source-1",
        watched_folder_id="wf-1",
    )

    assert payload["payload_version"] == 1
    assert payload["storage_source_id"] == "source-1"
    assert payload["watched_folder_id"] == "wf-1"
    assert payload["canonical_path"] == "/library/sample.jpg"
    assert payload["runtime_path"] == str(photo_path.resolve())
    assert payload["relative_path"] == "sample.jpg"
    assert payload["modified_mtime_ns"] == photo_path.stat().st_mtime_ns
    assert payload["idempotency_key"] == (
        f"wf-1:sample.jpg:{photo_path.stat().st_size}:{photo_path.stat().st_mtime_ns}"
    )
    assert payload["filesize"] == photo_path.stat().st_size
    assert "sha256" not in payload
    assert "thumbnail_jpeg" not in payload
    assert "thumbnail_mime_type" not in payload
    assert "thumbnail_width" not in payload
    assert "thumbnail_height" not in payload
    assert "faces_count" not in payload
    assert "detections" not in payload
    assert "modified_mtime_ns" in payload


def test_serialize_extracted_content_submission_includes_face_and_thumbnail_fields():
    from app.processing.ingest_persistence import (
        PhotoRecord,
        serialize_extracted_content_submission,
    )

    record = PhotoRecord(
        photo_id="photo-1",
        path="/library/sample.jpg",
        sha256="abc123",
        filesize=123,
        ext="jpg",
        created_ts=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
        modified_ts=datetime(2026, 4, 5, 12, 1, tzinfo=UTC),
        shot_ts=None,
        shot_ts_source=None,
        camera_make="Canon",
        camera_model="EOS",
        software=None,
        orientation="1",
        gps_latitude=None,
        gps_longitude=None,
        gps_altitude=None,
        thumbnail_jpeg=b"thumb",
        thumbnail_mime_type="image/jpeg",
        thumbnail_width=128,
        thumbnail_height=128,
        faces_count=1,
    )

    payload = serialize_extracted_content_submission(
        record=record,
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="sample.jpg",
        detections=[
            {
                "face_id": "face-1",
                "bbox_x": 1,
                "bbox_y": 2,
                "bbox_w": 3,
                "bbox_h": 4,
                "bitmap": b"face-bytes",
                "embedding": None,
                "provenance": {"detector": "opencv"},
            }
        ],
        warnings=["face detection failed for sidecar"],
    )

    assert payload["payload_version"] == 1
    assert payload["storage_source_id"] == "source-1"
    assert payload["watched_folder_id"] == "wf-1"
    assert payload["relative_path"] == "sample.jpg"
    assert payload["sha256"] == "abc123"
    assert payload["faces_count"] == 1
    assert payload["thumbnail_jpeg"] == "dGh1bWI="
    assert _decode_base64_text(payload["thumbnail_jpeg"]) == b"thumb"
    assert payload["thumbnail_mime_type"] == "image/jpeg"
    assert payload["thumbnail_width"] == 128
    assert payload["thumbnail_height"] == 128
    assert payload["detections"][0]["face_id"] == "face-1"
    assert payload["detections"][0]["bitmap"] == "ZmFjZS1ieXRlcw=="
    assert _decode_base64_text(payload["detections"][0]["bitmap"]) == b"face-bytes"
    assert payload["warnings"] == ["face detection failed for sidecar"]


def test_serialize_reused_content_submission_includes_json_safe_thumbnail_fields():
    from app.processing.ingest_persistence import (
        PhotoRecord,
        serialize_reused_content_submission,
    )

    record = PhotoRecord(
        photo_id="photo-1",
        path="/library/sample.jpg",
        sha256="abc123",
        filesize=123,
        ext="jpg",
        created_ts=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
        modified_ts=datetime(2026, 4, 5, 12, 1, tzinfo=UTC),
        shot_ts=None,
        shot_ts_source=None,
        camera_make=None,
        camera_model=None,
        software=None,
        orientation=None,
        gps_latitude=None,
        gps_longitude=None,
        gps_altitude=None,
        thumbnail_jpeg=b"thumb",
        thumbnail_mime_type="image/jpeg",
        thumbnail_width=128,
        thumbnail_height=128,
        faces_count=1,
    )

    payload = serialize_reused_content_submission(
        record=record,
        candidate_payload={
            "storage_source_id": "source-1",
            "watched_folder_id": "wf-1",
            "relative_path": "sample.jpg",
        },
        warnings=["reused existing content"],
    )

    assert payload["payload_version"] == 1
    assert payload["storage_source_id"] == "source-1"
    assert payload["watched_folder_id"] == "wf-1"
    assert payload["relative_path"] == "sample.jpg"
    assert payload["thumbnail_jpeg"] == "dGh1bWI="
    assert _decode_base64_text(payload["thumbnail_jpeg"]) == b"thumb"
    assert payload["detections"] == []
    assert payload["warnings"] == ["reused existing content"]


def test_lookup_existing_artifacts_by_sha_prefers_complete_duplicate_row(tmp_path):
    from app.processing.ingest_persistence import lookup_existing_artifacts_by_sha

    class FakeMappingsResult:
        def __init__(self, rows: list[dict]) -> None:
            self._rows = rows

        def all(self) -> list[dict]:
            return list(self._rows)

    class FakeExecuteResult:
        def __init__(self, rows: list[dict]) -> None:
            self._rows = rows

        def mappings(self) -> FakeMappingsResult:
            return FakeMappingsResult(self._rows)

    class FakeConnection:
        def __init__(self) -> None:
            self.photo_query_count = 0

        def execute(self, statement):
            compiled = str(statement)
            if "FROM photos" in compiled:
                self.photo_query_count += 1
                return FakeExecuteResult(
                    [
                        {
                            "photo_id": "incomplete-photo",
                            "shot_ts": None,
                            "shot_ts_source": None,
                            "camera_make": None,
                            "camera_model": None,
                            "software": None,
                            "orientation": None,
                            "gps_latitude": None,
                            "gps_longitude": None,
                            "gps_altitude": None,
                            "thumbnail_jpeg": None,
                            "thumbnail_mime_type": None,
                            "thumbnail_width": None,
                            "thumbnail_height": None,
                            "faces_count": 0,
                            "faces_detected_ts": None,
                        },
                        {
                            "photo_id": "complete-photo",
                            "shot_ts": None,
                            "shot_ts_source": None,
                            "camera_make": "Canon",
                            "camera_model": "EOS",
                            "software": None,
                            "orientation": "1",
                            "gps_latitude": None,
                            "gps_longitude": None,
                            "gps_altitude": None,
                            "thumbnail_jpeg": b"complete-thumbnail",
                            "thumbnail_mime_type": "image/jpeg",
                            "thumbnail_width": 64,
                            "thumbnail_height": 64,
                            "faces_count": 1,
                            "faces_detected_ts": datetime(2026, 4, 5, 12, 30, tzinfo=UTC),
                        },
                    ]
                )
            if "FROM faces" in compiled:
                return FakeExecuteResult(
                    [
                        {
                            "face_id": "face-1",
                            "person_id": None,
                            "bbox_x": 10,
                            "bbox_y": 11,
                            "bbox_w": 12,
                            "bbox_h": 13,
                            "bitmap": b"existing-face",
                            "embedding": None,
                            "provenance": {"detector": "existing"},
                        }
                    ]
                )
            raise AssertionError(f"unexpected statement: {compiled}")

    connection = FakeConnection()
    result = lookup_existing_artifacts_by_sha(connection, "same-sha")

    assert connection.photo_query_count == 1
    assert result is not None
    assert result["photo_id"] == "complete-photo"
    assert result["thumbnail_jpeg"] == b"complete-thumbnail"
    assert result["faces_count"] == 1
    assert result["detections"] == [
        {
            "face_id": "face-1",
            "person_id": None,
            "bbox_x": 10,
            "bbox_y": 11,
            "bbox_w": 12,
            "bbox_h": 13,
            "bitmap": b"existing-face",
            "embedding": None,
            "provenance": {"detector": "existing"},
        }
    ]


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
    assert _normalize_timestamp(row["updated_ts"]) == now + timedelta(minutes=1)


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
    assert _normalize_timestamp(row["faces_detected_ts"]) == detected_ts


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
                    "embedding": [0.1, 0.2],
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
