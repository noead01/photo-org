from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, insert

from app.migrations import upgrade_database
from app.storage import faces, photos

pytest.importorskip("PIL")
from PIL import Image


def _write_test_image(path: Path) -> None:
    image = Image.new("RGB", (4, 4), color=(255, 0, 0))
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


class StaticFaceDetector:
    def __init__(self, detections: list[dict]) -> None:
        self._detections = detections
        self.calls = 0
        self.paths: list[Path] = []

    def detect(self, path: Path) -> list[dict]:
        self.calls += 1
        self.paths.append(path)
        return list(self._detections)


class SettingsAwareFaceDetector(StaticFaceDetector):
    def __init__(self, detections: list[dict], *, settings: dict[str, object]) -> None:
        super().__init__(detections)
        self._settings = settings

    def detection_settings(self) -> dict[str, object]:
        return dict(self._settings)


class RaisingFaceDetector:
    def detect(self, path: Path) -> list[dict]:
        raise AssertionError("face detector should not have been called")


class RuntimeErrorFaceDetector:
    def __init__(self, message: str) -> None:
        self._message = message

    def detect(self, path: Path) -> list[dict]:
        raise RuntimeError(self._message)


class SettingsAwareRuntimeErrorFaceDetector(RuntimeErrorFaceDetector):
    def __init__(self, message: str, *, settings: dict[str, object]) -> None:
        super().__init__(message)
        self._settings = settings

    def detection_settings(self) -> dict[str, object]:
        return dict(self._settings)


def _detection_settings(
    *,
    scale_factor: float = 1.1,
    min_neighbors: int = 5,
    min_size: list[int] | None = None,
    max_size: list[int] | None = None,
    min_area_ratio: float = 0.0,
    max_area_ratio: float = 1.0,
    aspect_ratio_min: float = 0.0,
    aspect_ratio_max: float = 100.0,
) -> dict[str, object]:
    return {
        "detector": "opencv-haarcascade",
        "model": "haarcascade_frontalface_default",
        "scale_factor": scale_factor,
        "min_neighbors": min_neighbors,
        "min_size": min_size or [60, 60],
        "max_size": max_size,
        "min_area_ratio": min_area_ratio,
        "max_area_ratio": max_area_ratio,
        "aspect_ratio_min": aspect_ratio_min,
        "aspect_ratio_max": aspect_ratio_max,
    }


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


class FakeLookupConnection:
    def __init__(self, photo_rows: list[dict], face_rows_by_photo_id: dict[str, list[dict]]) -> None:
        self._photo_rows = photo_rows
        self._face_rows_by_photo_id = face_rows_by_photo_id
        self.photo_query_count = 0

    def execute(self, statement):
        compiled = str(statement)
        if "FROM photos" in compiled:
            self.photo_query_count += 1
            return FakeExecuteResult(self._photo_rows)

        if "FROM faces" in compiled:
            photo_id = statement.whereclause.right.value
            return FakeExecuteResult(self._face_rows_by_photo_id.get(photo_id, []))
        if "FROM photo_exif_attributes" in compiled:
            return FakeExecuteResult([])

        raise AssertionError(f"unexpected statement: {compiled}")


def test_lookup_existing_artifacts_by_sha_prefers_complete_row_when_first_match_is_incomplete():
    from app.processing.ingest_persistence import lookup_existing_artifacts_by_sha

    connection = FakeLookupConnection(
        photo_rows=[
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
                "faces_detected_ts": datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
            },
        ],
        face_rows_by_photo_id={
            "complete-photo": [
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
        },
    )

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


def test_process_candidate_payload_reuses_known_sha_without_invoking_metadata_extraction(tmp_path, monkeypatch):
    from app.services.ingest_extraction_worker import process_candidate_payload

    database_url = f"sqlite:///{tmp_path / 'ingest-worker-reuse.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    photo_path = tmp_path / "sample.jpg"
    _write_test_image(photo_path)
    record_sha = hashlib.sha256(photo_path.read_bytes()).hexdigest()

    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                _photo_row_values(
                    photo_id="existing-photo",
                    path="/library/already-imported.jpg",
                    sha256=record_sha,
                    now=now,
                    thumbnail_jpeg=b"existing-thumbnail",
                    thumbnail_mime_type="image/jpeg",
                    thumbnail_width=64,
                    thumbnail_height=64,
                    faces_count=0,
                    faces_detected_ts=now,
                )
            )
        )

    def _unexpected_build_photo_record_from_sha(*args, **kwargs):
        raise AssertionError("build_photo_record_from_sha should not run on the SHA reuse path")

    monkeypatch.setattr(
        "app.services.ingest_extraction_worker.build_photo_record_from_sha",
        _unexpected_build_photo_record_from_sha,
    )

    result = process_candidate_payload(
        database_url,
        payload={
            "storage_source_id": "source-1",
            "watched_folder_id": "wf-1",
            "canonical_path": "/library/sample.jpg",
            "runtime_path": str(photo_path),
            "relative_path": "sample.jpg",
        },
        face_detector=RaisingFaceDetector(),
    )

    assert result.reused_existing_artifacts is True
    assert result.analysis_performed is False
    assert not hasattr(result, "payload")
    assert not hasattr(result, "reused_existing")
    assert result.extracted_payload["sha256"] == record_sha
    assert result.extracted_payload["path"] == "/library/sample.jpg"
    assert result.extracted_payload["thumbnail_jpeg"] == "ZXhpc3RpbmctdGh1bWJuYWls"
    assert result.extracted_payload["faces_count"] == 0
    assert result.extracted_payload["detections"] == []


def test_process_candidate_payload_reuses_existing_detections_with_matching_settings(tmp_path):
    from app.services.ingest_extraction_worker import process_candidate_payload

    database_url = f"sqlite:///{tmp_path / 'ingest-worker-reuse-detections.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    photo_path = tmp_path / "sample.jpg"
    _write_test_image(photo_path)
    record_sha = hashlib.sha256(photo_path.read_bytes()).hexdigest()
    existing_settings = _detection_settings()

    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                _photo_row_values(
                    photo_id="existing-photo",
                    path="/library/already-imported.jpg",
                    sha256=record_sha,
                    now=now,
                    thumbnail_jpeg=b"existing-thumbnail",
                    thumbnail_mime_type="image/jpeg",
                    thumbnail_width=64,
                    thumbnail_height=64,
                    faces_count=1,
                    faces_detected_ts=now,
                )
            )
        )
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="existing-photo",
                person_id=None,
                bbox_x=10,
                bbox_y=11,
                bbox_w=12,
                bbox_h=13,
                bitmap=b"existing-face",
                embedding=None,
                provenance={
                    **existing_settings,
                    "bbox_space_width": 400,
                    "bbox_space_height": 300,
                },
            )
        )

    detector = SettingsAwareFaceDetector(
        detections=[
            {
                "face_id": "face-new",
                "person_id": None,
                "bbox_x": 15,
                "bbox_y": 16,
                "bbox_w": 17,
                "bbox_h": 18,
                "bitmap": b"new-face",
                "embedding": None,
                "provenance": {"detector": "fresh"},
            }
        ],
        settings=_detection_settings(),
    )

    result = process_candidate_payload(
        database_url,
        payload={
            "storage_source_id": "source-1",
            "watched_folder_id": "wf-1",
            "canonical_path": "/library/sample.jpg",
            "runtime_path": str(photo_path),
            "relative_path": "sample.jpg",
        },
        face_detector=detector,
    )

    assert result.reused_existing_artifacts is True
    assert result.analysis_performed is False
    assert detector.calls == 0
    assert detector.paths == []
    assert result.extracted_payload["faces_count"] == 1
    assert result.extracted_payload["detections"] == [
        {
            "face_id": "face-1",
            "person_id": None,
            "bbox_x": 10,
            "bbox_y": 11,
            "bbox_w": 12,
            "bbox_h": 13,
            "bitmap": "ZXhpc3RpbmctZmFjZQ==",
            "embedding": None,
            "provenance": {
                **existing_settings,
                "bbox_space_width": 400,
                "bbox_space_height": 300,
            },
        }
    ]


def test_process_candidate_payload_reruns_detection_when_settings_change_for_same_sha(tmp_path):
    from app.services.ingest_extraction_worker import process_candidate_payload

    database_url = f"sqlite:///{tmp_path / 'ingest-worker-reuse-refresh.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    photo_path = tmp_path / "sample.jpg"
    _write_test_image(photo_path)
    record_sha = hashlib.sha256(photo_path.read_bytes()).hexdigest()
    existing_settings = _detection_settings(scale_factor=1.1)
    updated_settings = _detection_settings(
        scale_factor=1.15,
        min_neighbors=9,
        min_size=[96, 96],
        max_size=[420, 420],
        min_area_ratio=0.01,
        max_area_ratio=0.45,
        aspect_ratio_min=0.75,
        aspect_ratio_max=1.35,
    )

    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                _photo_row_values(
                    photo_id="existing-photo",
                    path="/library/already-imported.jpg",
                    sha256=record_sha,
                    now=now,
                    thumbnail_jpeg=b"existing-thumbnail",
                    thumbnail_mime_type="image/jpeg",
                    thumbnail_width=64,
                    thumbnail_height=64,
                    faces_count=1,
                    faces_detected_ts=now,
                )
            )
        )
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="existing-photo",
                person_id=None,
                bbox_x=10,
                bbox_y=11,
                bbox_w=12,
                bbox_h=13,
                bitmap=b"existing-face",
                embedding=None,
                provenance={
                    **existing_settings,
                    "bbox_space_width": 400,
                    "bbox_space_height": 300,
                },
            )
        )

    detector = SettingsAwareFaceDetector(
        detections=[
            {
                "face_id": "face-new",
                "person_id": None,
                "bbox_x": 15,
                "bbox_y": 16,
                "bbox_w": 17,
                "bbox_h": 18,
                "bitmap": b"new-face",
                "embedding": None,
                "provenance": {
                    **updated_settings,
                    "bbox_space_width": 400,
                    "bbox_space_height": 300,
                },
            }
        ],
        settings=updated_settings,
    )

    result = process_candidate_payload(
        database_url,
        payload={
            "storage_source_id": "source-1",
            "watched_folder_id": "wf-1",
            "canonical_path": "/library/sample.jpg",
            "runtime_path": str(photo_path),
            "relative_path": "sample.jpg",
        },
        face_detector=detector,
    )

    assert result.reused_existing_artifacts is True
    assert result.analysis_performed is True
    assert detector.calls == 1
    assert detector.paths == [photo_path.resolve()]
    assert result.extracted_payload["faces_count"] == 1
    assert result.extracted_payload["detections"] == [
        {
            "face_id": "face-new",
            "person_id": None,
            "bbox_x": 15,
            "bbox_y": 16,
            "bbox_w": 17,
            "bbox_h": 18,
            "bitmap": "bmV3LWZhY2U=",
            "embedding": None,
            "provenance": {
                **updated_settings,
                "bbox_space_width": 400,
                "bbox_space_height": 300,
            },
        }
    ]


def test_process_candidate_payload_reuse_path_keeps_existing_detections_when_detector_fails(tmp_path):
    from app.services.ingest_extraction_worker import process_candidate_payload

    database_url = f"sqlite:///{tmp_path / 'ingest-worker-reuse-warning.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    photo_path = tmp_path / "sample.jpg"
    _write_test_image(photo_path)
    record_sha = hashlib.sha256(photo_path.read_bytes()).hexdigest()
    existing_settings = _detection_settings(scale_factor=1.1)
    updated_settings = _detection_settings(
        scale_factor=1.15,
        min_neighbors=9,
        min_size=[96, 96],
        max_size=[420, 420],
        min_area_ratio=0.01,
        max_area_ratio=0.45,
        aspect_ratio_min=0.75,
        aspect_ratio_max=1.35,
    )

    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                _photo_row_values(
                    photo_id="existing-photo",
                    path="/library/already-imported.jpg",
                    sha256=record_sha,
                    now=now,
                    thumbnail_jpeg=b"existing-thumbnail",
                    thumbnail_mime_type="image/jpeg",
                    thumbnail_width=64,
                    thumbnail_height=64,
                    faces_count=1,
                    faces_detected_ts=now,
                )
            )
        )
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="existing-photo",
                person_id=None,
                bbox_x=10,
                bbox_y=11,
                bbox_w=12,
                bbox_h=13,
                bitmap=b"existing-face",
                embedding=None,
                provenance={
                    **existing_settings,
                    "bbox_space_width": 400,
                    "bbox_space_height": 300,
                },
            )
        )

    result = process_candidate_payload(
        database_url,
        payload={
            "storage_source_id": "source-1",
            "watched_folder_id": "wf-1",
            "canonical_path": "/library/sample.jpg",
            "runtime_path": str(photo_path),
            "relative_path": "sample.jpg",
        },
        face_detector=SettingsAwareRuntimeErrorFaceDetector(
            "detector exploded",
            settings=updated_settings,
        ),
    )

    assert result.reused_existing_artifacts is True
    assert result.analysis_performed is False
    assert result.extracted_payload["faces_count"] == 1
    assert result.extracted_payload["warnings"] == [
        "face detection failed: detector exploded"
    ]
    assert result.extracted_payload["detections"] == [
        {
            "face_id": "face-1",
            "person_id": None,
            "bbox_x": 10,
            "bbox_y": 11,
            "bbox_w": 12,
            "bbox_h": 13,
            "bitmap": "ZXhpc3RpbmctZmFjZQ==",
            "embedding": None,
            "provenance": {
                **existing_settings,
                "bbox_space_width": 400,
                "bbox_space_height": 300,
            },
        }
    ]


def test_process_candidate_payload_extracts_new_sha_and_returns_detections(tmp_path):
    from app.services.ingest_extraction_worker import process_candidate_payload

    database_url = f"sqlite:///{tmp_path / 'ingest-worker-new.db'}"
    upgrade_database(database_url)

    photo_path = tmp_path / "sample.jpg"
    _write_test_image(photo_path)
    detector = StaticFaceDetector(
        detections=[
            {
                "face_id": "face-1",
                "bbox_x": 1,
                "bbox_y": 2,
                "bbox_w": 3,
                "bbox_h": 4,
                "bitmap": b"face-bitmap",
                "embedding": None,
                "provenance": {"detector": "test"},
                "person_id": None,
            }
        ]
    )

    result = process_candidate_payload(
        database_url,
        payload={
            "storage_source_id": "source-1",
            "watched_folder_id": "wf-1",
            "canonical_path": "/library/sample.jpg",
            "runtime_path": str(photo_path),
            "relative_path": "sample.jpg",
        },
        face_detector=detector,
    )

    assert detector.calls == 1
    assert result.reused_existing_artifacts is False
    assert result.analysis_performed is True
    assert not hasattr(result, "payload")
    assert not hasattr(result, "reused_existing")
    assert len(result.extracted_payload["sha256"]) == 64
    assert result.extracted_payload["path"] == "/library/sample.jpg"
    assert result.extracted_payload["thumbnail_jpeg"] is not None
    assert result.extracted_payload["thumbnail_mime_type"] == "image/jpeg"
    assert result.extracted_payload["faces_count"] == 1
    assert result.extracted_payload["detections"] == [
        {
            "face_id": "face-1",
            "bbox_x": 1,
            "bbox_y": 2,
            "bbox_w": 3,
            "bbox_h": 4,
            "bitmap": "ZmFjZS1iaXRtYXA=",
            "embedding": None,
            "provenance": {"detector": "test"},
            "person_id": None,
        }
    ]


def test_process_candidate_payload_keeps_thumbnail_failure_as_warning(tmp_path, monkeypatch):
    from app.services.ingest_extraction_worker import process_candidate_payload

    database_url = f"sqlite:///{tmp_path / 'ingest-worker-thumbnail-warning.db'}"
    upgrade_database(database_url)

    photo_path = tmp_path / "sample.jpg"
    _write_test_image(photo_path)
    detector = StaticFaceDetector(detections=[])

    def _raise_thumbnail_failure(path: Path):
        raise RuntimeError("thumbnail exploded")

    monkeypatch.setattr(
        "app.services.ingest_extraction_worker.generate_thumbnail",
        _raise_thumbnail_failure,
    )

    result = process_candidate_payload(
        database_url,
        payload={
            "storage_source_id": "source-1",
            "watched_folder_id": "wf-1",
            "canonical_path": "/library/sample.jpg",
            "runtime_path": str(photo_path),
            "relative_path": "sample.jpg",
        },
        face_detector=detector,
    )

    assert detector.calls == 1
    assert result.reused_existing_artifacts is False
    assert result.analysis_performed is True
    assert result.extracted_payload["thumbnail_jpeg"] is None
    assert result.extracted_payload["thumbnail_mime_type"] is None
    assert result.extracted_payload["thumbnail_width"] is None
    assert result.extracted_payload["thumbnail_height"] is None
    assert result.extracted_payload["faces_count"] == 0
    assert result.extracted_payload["warnings"] == [
        "thumbnail generation failed: thumbnail exploded"
    ]


def test_process_candidate_payload_keeps_face_detection_failure_as_warning(tmp_path):
    from app.services.ingest_extraction_worker import process_candidate_payload

    database_url = f"sqlite:///{tmp_path / 'ingest-worker-face-warning.db'}"
    upgrade_database(database_url)

    photo_path = tmp_path / "sample.jpg"
    _write_test_image(photo_path)

    result = process_candidate_payload(
        database_url,
        payload={
            "storage_source_id": "source-1",
            "watched_folder_id": "wf-1",
            "canonical_path": "/library/sample.jpg",
            "runtime_path": str(photo_path),
            "relative_path": "sample.jpg",
        },
        face_detector=RuntimeErrorFaceDetector("detector exploded"),
    )

    assert result.reused_existing_artifacts is False
    assert result.analysis_performed is True
    assert result.extracted_payload["thumbnail_jpeg"] is not None
    assert result.extracted_payload["faces_count"] == 0
    assert result.extracted_payload["detections"] == []
    assert result.extracted_payload["warnings"] == [
        "face detection failed: detector exploded"
    ]


def test_process_candidate_payload_converts_sha_reuse_stat_race_into_missing_file_error(
    tmp_path, monkeypatch
):
    from app.services.ingest_extraction_worker import (
        CandidateFileMissingError,
        process_candidate_payload,
    )

    database_url = f"sqlite:///{tmp_path / 'ingest-worker-reuse-missing-file.db'}"
    upgrade_database(database_url)
    engine = create_engine(database_url, future=True)
    now = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    photo_path = tmp_path / "sample.jpg"
    _write_test_image(photo_path)
    record_sha = hashlib.sha256(photo_path.read_bytes()).hexdigest()

    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                _photo_row_values(
                    photo_id="existing-photo",
                    path="/library/already-imported.jpg",
                    sha256=record_sha,
                    now=now,
                    thumbnail_jpeg=b"existing-thumbnail",
                    thumbnail_mime_type="image/jpeg",
                    thumbnail_width=64,
                    thumbnail_height=64,
                    faces_count=0,
                    faces_detected_ts=now,
                )
            )
        )

    def _raise_missing_stat(*args, **kwargs):
        raise FileNotFoundError("gone")

    monkeypatch.setattr(
        "app.services.ingest_extraction_worker._build_reused_photo_record",
        _raise_missing_stat,
    )

    with pytest.raises(CandidateFileMissingError, match="candidate file missing"):
        process_candidate_payload(
            database_url,
            payload={
                "storage_source_id": "source-1",
                "watched_folder_id": "wf-1",
                "canonical_path": "/library/sample.jpg",
                "runtime_path": str(photo_path),
                "relative_path": "sample.jpg",
            },
            face_detector=RaisingFaceDetector(),
        )
