from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.engine import Connection

from app.db.queue import IngestQueueStore
from app.migrations import upgrade_database
from app.processing.ingest_persistence import serialize_extracted_content_submission
from app.services.ingest_extraction_worker import ExtractionResult
from app.services import ingest_queue_processor
from app.services.ingest_queue_processor import (
    PROCESSING_LEASE_SECONDS,
    process_pending_ingest_queue,
)
from app.storage import faces, photo_files, photos, watched_folders
from photoorg_db_schema import ingest_queue, ingest_run_files, ingest_runs


SAMPLE_PAYLOAD = {
    "photo_id": "photo-1",
    "path": "queued/photo-1.heic",
    "sha256": "a" * 64,
    "filesize": 123,
    "ext": "heic",
    "created_ts": "2024-01-01T00:00:00+00:00",
    "modified_ts": "2024-01-02T00:00:00+00:00",
    "shot_ts": None,
    "shot_ts_source": None,
    "camera_make": None,
    "camera_model": None,
    "software": None,
    "orientation": None,
    "gps_latitude": None,
    "gps_longitude": None,
    "gps_altitude": None,
    "faces_count": 0,
}


def build_payload(**overrides):
    return {**SAMPLE_PAYLOAD, **overrides}


def load_photo_paths(database_url: str) -> list[str]:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        rows = connection.execute(select(photos.c.path).order_by(photos.c.path)).all()
    return [row[0] for row in rows]


def load_photo_detection_state(database_url: str, photo_id: str) -> tuple[int, datetime | None]:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        row = connection.execute(
            select(photos.c.faces_count, photos.c.faces_detected_ts).where(
                photos.c.photo_id == photo_id
            )
        ).one()
    return row[0], row[1]


def load_photo_row(database_url: str, photo_id: str) -> dict:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        row = connection.execute(
            select(photos).where(photos.c.photo_id == photo_id)
        ).mappings().one()
    return dict(row)


def load_face_rows(database_url: str, photo_id: str) -> list[dict]:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        rows = connection.execute(
            select(
                faces.c.face_id,
                faces.c.photo_id,
                faces.c.bbox_x,
                faces.c.bbox_y,
                faces.c.bbox_w,
                faces.c.bbox_h,
                faces.c.provenance,
            )
            .where(faces.c.photo_id == photo_id)
            .order_by(faces.c.face_id)
        ).mappings()
    return [dict(row) for row in rows]


def load_photo_file_rows(database_url: str, photo_id: str) -> list[dict]:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        rows = connection.execute(
            select(photo_files)
            .where(photo_files.c.photo_id == photo_id)
            .order_by(photo_files.c.relative_path)
        ).mappings()
    return [dict(row) for row in rows]


def load_ingest_runs(database_url: str) -> list[dict]:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        rows = connection.execute(
            select(ingest_runs).order_by(ingest_runs.c.started_ts, ingest_runs.c.ingest_run_id)
        ).mappings()
    return [dict(row) for row in rows]


def load_ingest_run_files(database_url: str) -> list[dict]:
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        rows = connection.execute(
            select(ingest_run_files).order_by(
                ingest_run_files.c.created_ts,
                ingest_run_files.c.ingest_run_file_id,
            )
        ).mappings()
    return [dict(row) for row in rows]


def mark_queue_row_processing(
    database_url: str,
    queue_id: str,
    *,
    last_attempt_ts: datetime,
) -> None:
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            update(ingest_queue)
            .where(ingest_queue.c.ingest_queue_id == queue_id)
            .values(
                status="processing",
                last_attempt_ts=last_attempt_ts,
            )
        )


def set_queue_row_enqueued_ts(
    database_url: str,
    queue_id: str,
    *,
    enqueued_ts: datetime,
) -> None:
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            update(ingest_queue)
            .where(ingest_queue.c.ingest_queue_id == queue_id)
            .values(enqueued_ts=enqueued_ts)
        )


def seed_existing_photo_with_same_photo_id(database_url: str) -> None:
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            photos.insert().values(
                photo_id=SAMPLE_PAYLOAD["photo_id"],
                path="existing/other-path.heic",
                sha256="b" * 64,
                phash=None,
                filesize=999,
                ext="heic",
                created_ts=datetime.now(tz=UTC),
                modified_ts=datetime.now(tz=UTC),
                shot_ts=None,
                shot_ts_source=None,
                camera_make=None,
                camera_model=None,
                software=None,
                orientation=None,
                gps_latitude=None,
                gps_longitude=None,
                gps_altitude=None,
                updated_ts=datetime.now(tz=UTC),
                faces_count=0,
                faces_detected_ts=None,
            )
        )


def test_process_pending_rows_applies_domain_write_and_marks_queue_complete(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-1",
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    assert result.processed == 1
    assert load_photo_paths(database_url) == [SAMPLE_PAYLOAD["path"]]
    assert queue_store.list_by_status("completed")


def test_process_pending_rows_is_idempotent_for_repeated_trigger_calls(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-idempotent.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-1",
    )

    first = process_pending_ingest_queue(database_url, limit=10)
    second = process_pending_ingest_queue(database_url, limit=10)

    assert first.processed == 1
    assert second.processed == 0


def test_process_pending_rows_records_ingest_run_with_created_updated_counts_and_warnings(
    tmp_path,
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-ingest-run-success.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=build_payload(),
        idempotency_key="photo-created",
    )
    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=build_payload(filesize=456, modified_ts="2024-01-03T00:00:00+00:00"),
        idempotency_key="photo-updated",
    )

    result = process_pending_ingest_queue(
        database_url,
        limit=10,
        face_detector=RaisingFaceDetector("detector exploded"),
    )

    run_rows = load_ingest_runs(database_url)
    file_rows = load_ingest_run_files(database_url)

    assert result.processed == 2
    assert result.failed == 0
    assert result.retryable_errors == 0

    assert len(run_rows) == 1
    assert run_rows[0]["status"] == "completed"
    assert run_rows[0]["completed_ts"] is not None
    assert run_rows[0]["files_seen"] == 2
    assert run_rows[0]["files_created"] == 1
    assert run_rows[0]["files_updated"] == 1
    assert run_rows[0]["files_missing"] == 0
    assert run_rows[0]["error_count"] == 2
    assert run_rows[0]["error_summary"] == "face detection failed: detector exploded"

    assert len(file_rows) == 2
    assert {row["ingest_queue_id"] for row in file_rows} == {
        row.ingest_queue_id for row in queue_store.list_by_status("completed")
    }
    assert {row["outcome"] for row in file_rows} == {"completed"}
    assert {
        row["error_detail"]
        for row in file_rows
    } == {"face detection failed: detector exploded"}


def test_process_pending_rows_marks_unsupported_payload_failed_without_stranding(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-unsupported.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="unknown_payload",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="bad-payload",
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    assert result.processed == 0
    assert result.failed == 1
    assert load_photo_paths(database_url) == []
    assert queue_store.list_by_status("processing") == []
    failed_rows = queue_store.list_by_status("failed")
    assert len(failed_rows) == 1
    assert failed_rows[0].attempt_count == 1
    assert "Unsupported payload_type" in failed_rows[0].last_error
    run_rows = load_ingest_runs(database_url)
    file_rows = load_ingest_run_files(database_url)
    assert len(run_rows) == 1
    assert run_rows[0]["status"] == "failed"
    assert run_rows[0]["files_seen"] == 1
    assert run_rows[0]["error_count"] == 1
    assert run_rows[0]["error_summary"] == "Unsupported payload_type: unknown_payload"
    assert len(file_rows) == 1
    assert file_rows[0]["outcome"] == "failed"
    assert file_rows[0]["error_detail"] == "Unsupported payload_type: unknown_payload"


def test_process_pending_rows_routes_ingest_candidate_to_extracted_payload_queue(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-ingest-candidate.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    candidate_payload = {
        "payload_version": 1,
        "storage_source_id": "source-1",
        "watched_folder_id": "wf-1",
        "canonical_path": "/library/candidate.jpg",
        "runtime_path": str((tmp_path / "candidate.jpg").resolve()),
        "relative_path": "candidate.jpg",
        "filesize": 123,
        "modified_ts": "2024-01-02T00:00:00+00:00",
        "modified_mtime_ns": 123456789,
        "idempotency_key": "wf-1:candidate.jpg:123:123456789",
    }
    queue_store.enqueue(
        payload_type="ingest_candidate",
        payload=candidate_payload,
        idempotency_key=candidate_payload["idempotency_key"],
    )

    extracted_payload = build_payload(
        photo_id="extracted-photo-1",
        path="/library/candidate.jpg",
        thumbnail_jpeg="dGh1bWI=",
        thumbnail_mime_type="image/jpeg",
        thumbnail_width=128,
        thumbnail_height=128,
        detections=[],
        warnings=[],
        payload_version=1,
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="candidate.jpg",
    )

    def fake_process_candidate_payload(database_url_arg, *, payload, face_detector=None):
        assert database_url_arg == database_url
        assert payload == candidate_payload
        return ExtractionResult(
            extracted_payload=extracted_payload,
            reused_existing_artifacts=False,
            analysis_performed=True,
        )

    monkeypatch.setattr(
        ingest_queue_processor,
        "process_candidate_payload",
        fake_process_candidate_payload,
        raising=False,
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    completed_rows = queue_store.list_by_status("completed")
    pending_rows = queue_store.list_by_status("pending")
    run_rows = load_ingest_runs(database_url)
    file_rows = load_ingest_run_files(database_url)

    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert len(completed_rows) == 1
    assert completed_rows[0].payload_type == "ingest_candidate"
    assert completed_rows[0].payload_json == candidate_payload
    assert completed_rows[0].last_error is None
    assert len(pending_rows) == 1
    assert pending_rows[0].payload_type == "extracted_photo"
    assert pending_rows[0].payload_json == extracted_payload
    assert pending_rows[0].idempotency_key == f"extracted:{extracted_payload['photo_id']}"
    assert load_photo_paths(database_url) == []
    assert len(run_rows) == 1
    assert run_rows[0]["status"] == "completed"
    assert run_rows[0]["files_seen"] == 1
    assert run_rows[0]["files_created"] == 0
    assert run_rows[0]["files_updated"] == 0
    assert run_rows[0]["error_count"] == 0
    assert len(file_rows) == 1
    assert file_rows[0]["path"] == candidate_payload["canonical_path"]
    assert file_rows[0]["outcome"] == "completed"
    assert file_rows[0]["error_detail"] is None


def test_process_pending_rows_scopes_extracted_photo_idempotency_key_away_from_legacy_rows(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-ingest-candidate-idempotency.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    legacy_payload = build_payload(photo_id="shared-photo-id", path="queued/legacy.heic")
    legacy_queue_id = queue_store.enqueue(
        payload_type="photo_metadata",
        payload=legacy_payload,
        idempotency_key="shared-photo-id",
    )
    mark_queue_row_processing(
        database_url,
        legacy_queue_id,
        last_attempt_ts=datetime.now(tz=UTC),
    )

    candidate_payload = {
        "payload_version": 1,
        "storage_source_id": "source-1",
        "watched_folder_id": "wf-1",
        "canonical_path": "/library/candidate-collision.jpg",
        "runtime_path": str((tmp_path / "candidate-collision.jpg").resolve()),
        "relative_path": "candidate-collision.jpg",
        "filesize": 123,
        "modified_ts": "2024-01-02T00:00:00+00:00",
        "modified_mtime_ns": 123456789,
        "idempotency_key": "wf-1:candidate-collision.jpg:123:123456789",
    }
    queue_store.enqueue(
        payload_type="ingest_candidate",
        payload=candidate_payload,
        idempotency_key=candidate_payload["idempotency_key"],
    )

    extracted_payload = build_payload(
        photo_id="shared-photo-id",
        path="/library/candidate-collision.jpg",
        thumbnail_jpeg="dGh1bWI=",
        thumbnail_mime_type="image/jpeg",
        thumbnail_width=128,
        thumbnail_height=128,
        detections=[],
        warnings=[],
        payload_version=1,
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="candidate-collision.jpg",
    )

    def fake_process_candidate_payload(database_url_arg, *, payload, face_detector=None):
        assert database_url_arg == database_url
        assert payload == candidate_payload
        return ExtractionResult(
            extracted_payload=extracted_payload,
            reused_existing_artifacts=False,
            analysis_performed=True,
        )

    monkeypatch.setattr(
        ingest_queue_processor,
        "process_candidate_payload",
        fake_process_candidate_payload,
        raising=False,
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    pending_rows = queue_store.list_by_status("pending")
    processing_rows = queue_store.list_by_status("processing")
    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert len(processing_rows) == 1
    assert processing_rows[0].ingest_queue_id == legacy_queue_id
    assert len(pending_rows) == 1
    extracted_row = next(row for row in pending_rows if row.payload_type == "extracted_photo")
    assert extracted_row.payload_json == extracted_payload
    assert extracted_row.idempotency_key == "extracted:shared-photo-id"


def test_process_pending_rows_records_canonical_path_for_retryable_ingest_candidate_failure(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-ingest-candidate-failure.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    candidate_payload = {
        "payload_version": 1,
        "storage_source_id": "source-1",
        "watched_folder_id": "wf-1",
        "canonical_path": "/library/candidate-failure.jpg",
        "runtime_path": str((tmp_path / "candidate-failure.jpg").resolve()),
        "relative_path": "candidate-failure.jpg",
        "filesize": 123,
        "modified_ts": "2024-01-02T00:00:00+00:00",
        "modified_mtime_ns": 123456789,
        "idempotency_key": "wf-1:candidate-failure.jpg:123:123456789",
    }
    queue_id = queue_store.enqueue(
        payload_type="ingest_candidate",
        payload=candidate_payload,
        idempotency_key=candidate_payload["idempotency_key"],
    )

    def failing_process_candidate_payload(database_url_arg, *, payload, face_detector=None):
        assert database_url_arg == database_url
        assert payload == candidate_payload
        raise RuntimeError("staged extraction exploded")

    monkeypatch.setattr(
        ingest_queue_processor,
        "process_candidate_payload",
        failing_process_candidate_payload,
        raising=False,
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    run_rows = load_ingest_runs(database_url)
    file_rows = load_ingest_run_files(database_url)

    assert result.processed == 0
    assert result.failed == 0
    assert result.retryable_errors == 1
    assert len(run_rows) == 1
    assert run_rows[0]["status"] == "partial"
    assert run_rows[0]["files_seen"] == 1
    assert run_rows[0]["error_count"] == 1
    assert run_rows[0]["error_summary"] == "staged extraction exploded"
    assert len(file_rows) == 1
    assert file_rows[0]["ingest_queue_id"] == queue_id
    assert file_rows[0]["path"] == candidate_payload["canonical_path"]
    assert file_rows[0]["outcome"] == "retryable_error"
    assert file_rows[0]["error_detail"] == "staged extraction exploded"


def test_process_pending_rows_persists_candidate_warning_payloads_instead_of_retrying(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-ingest-candidate-warning.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    candidate_payload = {
        "payload_version": 1,
        "storage_source_id": "source-1",
        "watched_folder_id": "wf-1",
        "canonical_path": "/library/candidate-warning.jpg",
        "runtime_path": str((tmp_path / "candidate-warning.jpg").resolve()),
        "relative_path": "candidate-warning.jpg",
        "filesize": 123,
        "modified_ts": "2024-01-02T00:00:00+00:00",
        "modified_mtime_ns": 123456789,
        "idempotency_key": "wf-1:candidate-warning.jpg:123:123456789",
    }
    queue_store.enqueue(
        payload_type="ingest_candidate",
        payload=candidate_payload,
        idempotency_key=candidate_payload["idempotency_key"],
    )

    extracted_payload = build_payload(
        photo_id="candidate-warning-photo",
        path="/library/candidate-warning.jpg",
        thumbnail_jpeg=None,
        thumbnail_mime_type=None,
        thumbnail_width=None,
        thumbnail_height=None,
        detections=[],
        warnings=["thumbnail generation failed: thumbnail exploded"],
        payload_version=1,
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="candidate-warning.jpg",
    )

    def fake_process_candidate_payload(database_url_arg, *, payload, face_detector=None):
        assert database_url_arg == database_url
        assert payload == candidate_payload
        return ExtractionResult(
            extracted_payload=extracted_payload,
            reused_existing_artifacts=False,
            analysis_performed=True,
        )

    monkeypatch.setattr(
        ingest_queue_processor,
        "process_candidate_payload",
        fake_process_candidate_payload,
        raising=False,
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    completed_rows = queue_store.list_by_status("completed")
    pending_rows = queue_store.list_by_status("pending")
    file_rows = load_ingest_run_files(database_url)

    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert len(completed_rows) == 1
    assert completed_rows[0].payload_type == "ingest_candidate"
    assert completed_rows[0].last_error == "thumbnail generation failed: thumbnail exploded"
    assert len(pending_rows) == 1
    assert pending_rows[0].payload_type == "extracted_photo"
    assert pending_rows[0].payload_json == extracted_payload
    assert len(file_rows) == 1
    assert file_rows[0]["outcome"] == "completed"
    assert file_rows[0]["error_detail"] == "thumbnail generation failed: thumbnail exploded"


def test_process_pending_rows_revives_failed_extracted_photo_row_on_idempotency_collision(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-ingest-candidate-revive.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    candidate_payload = {
        "payload_version": 1,
        "storage_source_id": "source-1",
        "watched_folder_id": "wf-1",
        "canonical_path": "/library/candidate-revive.jpg",
        "runtime_path": str((tmp_path / "candidate-revive.jpg").resolve()),
        "relative_path": "candidate-revive.jpg",
        "filesize": 123,
        "modified_ts": "2024-01-02T00:00:00+00:00",
        "modified_mtime_ns": 123456789,
        "idempotency_key": "wf-1:candidate-revive.jpg:123:123456789",
    }
    candidate_queue_id = queue_store.enqueue(
        payload_type="ingest_candidate",
        payload=candidate_payload,
        idempotency_key=candidate_payload["idempotency_key"],
    )

    stale_extracted_payload = build_payload(
        photo_id="shared-photo-id",
        path="/library/stale.jpg",
    )
    extracted_queue_id = queue_store.enqueue(
        payload_type="extracted_photo",
        payload=stale_extracted_payload,
        idempotency_key="extracted:shared-photo-id",
    )
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    set_queue_row_enqueued_ts(database_url, candidate_queue_id, enqueued_ts=base_time)
    set_queue_row_enqueued_ts(
        database_url,
        extracted_queue_id,
        enqueued_ts=base_time + timedelta(seconds=1),
    )
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            update(ingest_queue)
            .where(ingest_queue.c.ingest_queue_id == extracted_queue_id)
            .values(
                status="failed",
                last_error="old failure",
                processed_ts=datetime.now(tz=UTC),
            )
        )

    refreshed_payload = build_payload(
        photo_id="shared-photo-id",
        path="/library/candidate-revive.jpg",
        thumbnail_jpeg="dGh1bWI=",
        thumbnail_mime_type="image/jpeg",
        thumbnail_width=128,
        thumbnail_height=128,
        detections=[],
        warnings=[],
        payload_version=1,
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="candidate-revive.jpg",
    )

    def fake_process_candidate_payload(database_url_arg, *, payload, face_detector=None):
        assert database_url_arg == database_url
        assert payload == candidate_payload
        return ExtractionResult(
            extracted_payload=refreshed_payload,
            reused_existing_artifacts=False,
            analysis_performed=True,
        )

    monkeypatch.setattr(
        ingest_queue_processor,
        "process_candidate_payload",
        fake_process_candidate_payload,
        raising=False,
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    completed_rows = queue_store.list_by_status("completed")
    pending_rows = queue_store.list_by_status("pending")
    failed_rows = queue_store.list_by_status("failed")

    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert len(completed_rows) == 1
    assert completed_rows[0].payload_type == "ingest_candidate"
    assert failed_rows == []
    assert len(pending_rows) == 1
    assert pending_rows[0].ingest_queue_id == extracted_queue_id
    assert pending_rows[0].payload_type == "extracted_photo"
    assert pending_rows[0].payload_json == refreshed_payload
    assert pending_rows[0].last_error is None


def test_process_pending_rows_requeues_completed_extracted_photo_row_when_payload_refreshes(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-ingest-candidate-refresh-completed.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    candidate_payload = {
        "payload_version": 1,
        "storage_source_id": "source-1",
        "watched_folder_id": "wf-1",
        "canonical_path": "/library/candidate-refresh.jpg",
        "runtime_path": str((tmp_path / "candidate-refresh.jpg").resolve()),
        "relative_path": "candidate-refresh.jpg",
        "filesize": 123,
        "modified_ts": "2024-01-02T00:00:00+00:00",
        "modified_mtime_ns": 123456789,
        "idempotency_key": "wf-1:candidate-refresh.jpg:123:123456789",
    }
    candidate_queue_id = queue_store.enqueue(
        payload_type="ingest_candidate",
        payload=candidate_payload,
        idempotency_key=candidate_payload["idempotency_key"],
    )

    stale_extracted_payload = build_payload(
        photo_id="shared-photo-id",
        path="/library/stale.jpg",
        detections=[],
        warnings=["face detection failed: detector exploded"],
        payload_version=1,
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="candidate-refresh.jpg",
    )
    extracted_queue_id = queue_store.enqueue(
        payload_type="extracted_photo",
        payload=stale_extracted_payload,
        idempotency_key="extracted:shared-photo-id",
    )
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    set_queue_row_enqueued_ts(database_url, candidate_queue_id, enqueued_ts=base_time)
    set_queue_row_enqueued_ts(
        database_url,
        extracted_queue_id,
        enqueued_ts=base_time + timedelta(seconds=1),
    )
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            update(ingest_queue)
            .where(ingest_queue.c.ingest_queue_id == extracted_queue_id)
            .values(
                status="completed",
                last_error="face detection failed: detector exploded",
                processed_ts=datetime.now(tz=UTC),
            )
        )

    refreshed_payload = build_payload(
        photo_id="shared-photo-id",
        path="/library/candidate-refresh.jpg",
        thumbnail_jpeg="dGh1bWI=",
        thumbnail_mime_type="image/jpeg",
        thumbnail_width=128,
        thumbnail_height=128,
        detections=[
            {
                "face_id": "face-1",
                "bbox_x": 1,
                "bbox_y": 2,
                "bbox_w": 3,
                "bbox_h": 4,
                "bitmap": "ZmFjZS1iaXRtYXA=",
                "embedding": None,
                "provenance": {"detector": "fresh"},
            }
        ],
        warnings=[],
        payload_version=1,
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="candidate-refresh.jpg",
    )

    def fake_process_candidate_payload(database_url_arg, *, payload, face_detector=None):
        assert database_url_arg == database_url
        assert payload == candidate_payload
        return ExtractionResult(
            extracted_payload=refreshed_payload,
            reused_existing_artifacts=False,
            analysis_performed=True,
        )

    monkeypatch.setattr(
        ingest_queue_processor,
        "process_candidate_payload",
        fake_process_candidate_payload,
        raising=False,
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    completed_rows = queue_store.list_by_status("completed")
    pending_rows = queue_store.list_by_status("pending")
    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert len(completed_rows) == 1
    assert completed_rows[0].payload_type == "ingest_candidate"
    assert len(pending_rows) == 1
    assert pending_rows[0].ingest_queue_id == extracted_queue_id
    assert pending_rows[0].payload_type == "extracted_photo"
    assert pending_rows[0].payload_json == refreshed_payload
    assert pending_rows[0].last_error is None


def test_process_pending_rows_refreshes_pending_extracted_photo_row_when_payload_refreshes(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-ingest-candidate-refresh-pending.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    candidate_payload = {
        "payload_version": 1,
        "storage_source_id": "source-1",
        "watched_folder_id": "wf-1",
        "canonical_path": "/library/candidate-refresh-pending.jpg",
        "runtime_path": str((tmp_path / "candidate-refresh-pending.jpg").resolve()),
        "relative_path": "candidate-refresh-pending.jpg",
        "filesize": 123,
        "modified_ts": "2024-01-02T00:00:00+00:00",
        "modified_mtime_ns": 123456789,
        "idempotency_key": "wf-1:candidate-refresh-pending.jpg:123:123456789",
    }
    candidate_queue_id = queue_store.enqueue(
        payload_type="ingest_candidate",
        payload=candidate_payload,
        idempotency_key=candidate_payload["idempotency_key"],
    )

    stale_extracted_payload = build_payload(
        photo_id="shared-photo-id",
        path="/library/stale-pending.jpg",
        detections=[],
        warnings=["face detection failed: detector exploded"],
        payload_version=1,
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="candidate-refresh-pending.jpg",
    )
    extracted_queue_id = queue_store.enqueue(
        payload_type="extracted_photo",
        payload=stale_extracted_payload,
        idempotency_key="extracted:shared-photo-id",
    )
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    set_queue_row_enqueued_ts(database_url, candidate_queue_id, enqueued_ts=base_time)
    set_queue_row_enqueued_ts(
        database_url,
        extracted_queue_id,
        enqueued_ts=base_time + timedelta(seconds=1),
    )

    refreshed_payload = build_payload(
        photo_id="shared-photo-id",
        path="/library/candidate-refresh-pending.jpg",
        thumbnail_jpeg="dGh1bWI=",
        thumbnail_mime_type="image/jpeg",
        thumbnail_width=128,
        thumbnail_height=128,
        detections=[
            {
                "face_id": "face-1",
                "bbox_x": 1,
                "bbox_y": 2,
                "bbox_w": 3,
                "bbox_h": 4,
                "bitmap": "ZmFjZS1iaXRtYXA=",
                "embedding": None,
                "provenance": {"detector": "fresh"},
            }
        ],
        warnings=[],
        payload_version=1,
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="candidate-refresh-pending.jpg",
    )

    def fake_process_candidate_payload(database_url_arg, *, payload, face_detector=None):
        assert database_url_arg == database_url
        assert payload == candidate_payload
        return ExtractionResult(
            extracted_payload=refreshed_payload,
            reused_existing_artifacts=False,
            analysis_performed=True,
        )

    monkeypatch.setattr(
        ingest_queue_processor,
        "process_candidate_payload",
        fake_process_candidate_payload,
        raising=False,
    )

    result = process_pending_ingest_queue(database_url, limit=1)

    completed_rows = queue_store.list_by_status("completed")
    pending_rows = queue_store.list_by_status("pending")
    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert len(completed_rows) == 1
    assert completed_rows[0].payload_type == "ingest_candidate"
    assert len(pending_rows) == 1
    assert pending_rows[0].ingest_queue_id == extracted_queue_id
    assert pending_rows[0].payload_type == "extracted_photo"
    assert pending_rows[0].payload_json == refreshed_payload
    assert pending_rows[0].last_error is None


def test_process_pending_rows_records_failed_and_retryable_file_outcomes(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-ingest-run-errors.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    unsupported_queue_id = queue_store.enqueue(
        payload_type="unknown_payload",
        payload=build_payload(path="queued/unsupported.heic"),
        idempotency_key="unsupported-payload",
    )
    retryable_payload = build_payload(
        photo_id="photo-retryable",
        path="queued/retryable.heic",
    )
    retryable_queue_id = queue_store.enqueue(
        payload_type="photo_metadata",
        payload=retryable_payload,
        idempotency_key="retryable-payload",
    )

    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    set_queue_row_enqueued_ts(database_url, unsupported_queue_id, enqueued_ts=base_time)
    set_queue_row_enqueued_ts(
        database_url,
        retryable_queue_id,
        enqueued_ts=base_time + timedelta(seconds=1),
    )

    original_upsert = ingest_queue_processor.upsert_photo

    def flaky_upsert(connection, record):
        if record.path == retryable_payload["path"]:
            raise RuntimeError("transient db outage")
        return original_upsert(connection, record)

    monkeypatch.setattr(ingest_queue_processor, "upsert_photo", flaky_upsert)

    result = process_pending_ingest_queue(database_url, limit=10)

    run_rows = load_ingest_runs(database_url)
    file_rows = load_ingest_run_files(database_url)
    file_rows_by_queue_id = {row["ingest_queue_id"]: row for row in file_rows}

    assert result.processed == 0
    assert result.failed == 1
    assert result.retryable_errors == 1

    assert len(run_rows) == 1
    assert run_rows[0]["status"] == "partial"
    assert run_rows[0]["completed_ts"] is not None
    assert run_rows[0]["files_seen"] == 2
    assert run_rows[0]["files_created"] == 0
    assert run_rows[0]["files_updated"] == 0
    assert run_rows[0]["files_missing"] == 0
    assert run_rows[0]["error_count"] == 2
    assert (
        run_rows[0]["error_summary"]
        == "Unsupported payload_type: unknown_payload\ntransient db outage"
    )

    assert len(file_rows) == 2
    assert file_rows_by_queue_id[unsupported_queue_id]["path"] == "queued/unsupported.heic"
    assert file_rows_by_queue_id[unsupported_queue_id]["outcome"] == "failed"
    assert (
        "Unsupported payload_type"
        in file_rows_by_queue_id[unsupported_queue_id]["error_detail"]
    )
    assert file_rows_by_queue_id[retryable_queue_id]["path"] == retryable_payload["path"]
    assert file_rows_by_queue_id[retryable_queue_id]["outcome"] == "retryable_error"
    assert "transient db outage" in file_rows_by_queue_id[retryable_queue_id]["error_detail"]


def test_process_pending_rows_summarizes_distinct_errors_in_first_seen_order(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-ingest-run-summary.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_id_a = queue_store.enqueue(
        payload_type="unsupported_a",
        payload=build_payload(path="queued/a.heic"),
        idempotency_key="unsupported-a",
    )
    queue_id_b = queue_store.enqueue(
        payload_type="unsupported_b",
        payload=build_payload(path="queued/b.heic", photo_id="photo-b"),
        idempotency_key="unsupported-b",
    )
    queue_id_c = queue_store.enqueue(
        payload_type="unsupported_c",
        payload=build_payload(path="queued/c.heic", photo_id="photo-c"),
        idempotency_key="unsupported-c",
    )
    queue_id_d = queue_store.enqueue(
        payload_type="unsupported_d",
        payload=build_payload(path="queued/d.heic", photo_id="photo-d"),
        idempotency_key="unsupported-d",
    )

    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    set_queue_row_enqueued_ts(database_url, queue_id_a, enqueued_ts=base_time)
    set_queue_row_enqueued_ts(
        database_url,
        queue_id_b,
        enqueued_ts=base_time + timedelta(seconds=1),
    )
    set_queue_row_enqueued_ts(
        database_url,
        queue_id_c,
        enqueued_ts=base_time + timedelta(seconds=2),
    )
    set_queue_row_enqueued_ts(
        database_url,
        queue_id_d,
        enqueued_ts=base_time + timedelta(seconds=3),
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    run_rows = load_ingest_runs(database_url)

    assert result.processed == 0
    assert result.failed == 4
    assert result.retryable_errors == 0
    assert len(run_rows) == 1
    assert run_rows[0]["status"] == "failed"
    assert run_rows[0]["error_count"] == 4
    assert (
        run_rows[0]["error_summary"]
        == "Unsupported payload_type: unsupported_a\n"
        "Unsupported payload_type: unsupported_b\n"
        "Unsupported payload_type: unsupported_c\n"
        "(+1 more distinct errors)"
    )


def test_process_pending_rows_persists_detected_faces_for_photo_metadata(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-faces.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-with-faces",
    )

    result = process_pending_ingest_queue(
        database_url,
        limit=10,
        face_detector=StaticFaceDetector(
            detections=[
                {
                    "face_id": "face-1",
                    "bbox_x": 10,
                    "bbox_y": 20,
                    "bbox_w": 30,
                    "bbox_h": 40,
                    "bitmap": None,
                    "embedding": None,
                    "provenance": {"detector": "test-detector"},
                }
            ]
        ),
    )

    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert load_face_rows(database_url, SAMPLE_PAYLOAD["photo_id"]) == [
        {
            "face_id": "face-1",
            "photo_id": SAMPLE_PAYLOAD["photo_id"],
            "bbox_x": 10,
            "bbox_y": 20,
            "bbox_w": 30,
            "bbox_h": 40,
            "provenance": {"detector": "test-detector"},
        }
    ]
    faces_count, faces_detected_ts = load_photo_detection_state(
        database_url, SAMPLE_PAYLOAD["photo_id"]
    )
    assert faces_count == 1
    assert faces_detected_ts is not None
    completed_rows = queue_store.list_by_status("completed")
    assert len(completed_rows) == 1
    assert completed_rows[0].last_error is None


def test_process_pending_rows_persists_payload_faces_for_extracted_photo_without_detection(
    tmp_path,
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-extracted-photo.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(watched_folders).values(
                watched_folder_id="wf-1",
                scan_path="/library/imports",
                storage_source_id="source-1",
                relative_path="imports",
                display_name="Imports",
                is_enabled=1,
                availability_state="active",
                created_ts=datetime(2024, 1, 1, tzinfo=UTC),
                updated_ts=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )

    extracted_payload = serialize_extracted_content_submission(
        record=ingest_queue_processor.PhotoRecord(
            photo_id="photo-extracted-1",
            path="/library/extracted.jpg",
            sha256="c" * 64,
            filesize=123,
            ext="jpg",
            created_ts=datetime(2024, 1, 1, tzinfo=UTC),
            modified_ts=datetime(2024, 1, 2, tzinfo=UTC),
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
            thumbnail_height=96,
            faces_count=1,
        ),
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="extracted.jpg",
        detections=[
            {
                "face_id": "face-from-payload",
                "bbox_x": 11,
                "bbox_y": 22,
                "bbox_w": 33,
                "bbox_h": 44,
                "bitmap": b"face-bitmap",
                "embedding": None,
                "provenance": {"detector": "staged"},
            }
        ],
        warnings=[],
    )
    queue_store.enqueue(
        payload_type="extracted_photo",
        payload=extracted_payload,
        idempotency_key=f"extracted:{extracted_payload['photo_id']}",
    )

    result = process_pending_ingest_queue(
        database_url,
        limit=10,
        face_detector=RaisingFaceDetector("should not run"),
    )

    run_rows = load_ingest_runs(database_url)
    file_rows = load_ingest_run_files(database_url)

    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert load_photo_paths(database_url) == ["/library/extracted.jpg"]
    assert load_face_rows(database_url, "photo-extracted-1") == [
        {
            "face_id": "face-from-payload",
            "photo_id": "photo-extracted-1",
            "bbox_x": 11,
            "bbox_y": 22,
            "bbox_w": 33,
            "bbox_h": 44,
            "provenance": {"detector": "staged"},
        }
    ]
    faces_count, faces_detected_ts = load_photo_detection_state(
        database_url, "photo-extracted-1"
    )
    assert faces_count == 1
    assert faces_detected_ts is not None
    completed_rows = queue_store.list_by_status("completed")
    assert len(completed_rows) == 1
    assert completed_rows[0].payload_type == "extracted_photo"
    assert completed_rows[0].last_error is None
    photo_file_rows = load_photo_file_rows(database_url, "photo-extracted-1")
    assert len(photo_file_rows) == 1
    assert photo_file_rows[0]["photo_id"] == "photo-extracted-1"
    assert photo_file_rows[0]["watched_folder_id"] == "wf-1"
    assert photo_file_rows[0]["relative_path"] == "extracted.jpg"
    assert photo_file_rows[0]["filename"] == "extracted.jpg"
    assert photo_file_rows[0]["extension"] == "jpg"
    assert photo_file_rows[0]["filesize"] == 123
    assert photo_file_rows[0]["lifecycle_state"] == "active"
    assert photo_file_rows[0]["missing_ts"] is None
    assert photo_file_rows[0]["deleted_ts"] is None
    assert len(run_rows) == 1
    assert run_rows[0]["status"] == "completed"
    assert run_rows[0]["files_seen"] == 1
    assert run_rows[0]["files_created"] == 1
    assert run_rows[0]["files_updated"] == 0
    assert run_rows[0]["error_count"] == 0
    assert len(file_rows) == 1
    assert file_rows[0]["path"] == "/library/extracted.jpg"
    assert file_rows[0]["outcome"] == "completed"
    assert file_rows[0]["error_detail"] is None


def test_process_pending_rows_does_not_mark_face_detection_complete_when_payload_has_warning(
    tmp_path,
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-extracted-photo-face-warning.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(watched_folders).values(
                watched_folder_id="wf-1",
                scan_path="/library/imports",
                storage_source_id="source-1",
                relative_path="imports",
                display_name="Imports",
                is_enabled=1,
                availability_state="active",
                created_ts=datetime(2024, 1, 1, tzinfo=UTC),
                updated_ts=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )

    extracted_payload = serialize_extracted_content_submission(
        record=ingest_queue_processor.PhotoRecord(
            photo_id="photo-extracted-warning",
            path="/library/extracted-warning.jpg",
            sha256="e" * 64,
            filesize=123,
            ext="jpg",
            created_ts=datetime(2024, 1, 1, tzinfo=UTC),
            modified_ts=datetime(2024, 1, 2, tzinfo=UTC),
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
            thumbnail_height=96,
            faces_count=0,
        ),
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="extracted-warning.jpg",
        detections=[],
        warnings=["face detection failed: detector exploded"],
    )
    queue_store.enqueue(
        payload_type="extracted_photo",
        payload=extracted_payload,
        idempotency_key=f"extracted:{extracted_payload['photo_id']}",
    )

    result = process_pending_ingest_queue(
        database_url,
        limit=10,
        face_detector=RaisingFaceDetector("should not run"),
    )

    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert load_face_rows(database_url, "photo-extracted-warning") == []
    faces_count, faces_detected_ts = load_photo_detection_state(
        database_url, "photo-extracted-warning"
    )
    assert faces_count == 0
    assert faces_detected_ts is None


def test_process_pending_rows_reuses_existing_photo_row_for_duplicate_sha_extracted_payload(
    tmp_path,
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-extracted-photo-duplicate-sha.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(watched_folders).values(
                watched_folder_id="wf-1",
                scan_path="/library/imports",
                storage_source_id="source-1",
                relative_path="imports",
                display_name="Imports",
                is_enabled=1,
                availability_state="active",
                created_ts=datetime(2024, 1, 1, tzinfo=UTC),
                updated_ts=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        connection.execute(
            insert(photos).values(
                photo_id="photo-existing",
                path="/library/original.jpg",
                sha256="d" * 64,
                phash=None,
                filesize=100,
                ext="jpg",
                created_ts=datetime(2024, 1, 1, tzinfo=UTC),
                modified_ts=datetime(2024, 1, 1, tzinfo=UTC),
                shot_ts=None,
                shot_ts_source=None,
                camera_make=None,
                camera_model=None,
                software=None,
                orientation=None,
                gps_latitude=None,
                gps_longitude=None,
                gps_altitude=None,
                thumbnail_jpeg=b"old-thumb",
                thumbnail_mime_type="image/jpeg",
                thumbnail_width=64,
                thumbnail_height=64,
                updated_ts=datetime(2024, 1, 1, tzinfo=UTC),
                deleted_ts=None,
                faces_count=1,
                faces_detected_ts=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
    extracted_payload = serialize_extracted_content_submission(
        record=ingest_queue_processor.PhotoRecord(
            photo_id="photo-new-path",
            path="/library/duplicate.jpg",
            sha256="d" * 64,
            filesize=123,
            ext="jpg",
            created_ts=datetime(2024, 1, 2, tzinfo=UTC),
            modified_ts=datetime(2024, 1, 3, tzinfo=UTC),
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
            thumbnail_height=96,
            faces_count=1,
        ),
        storage_source_id="source-1",
        watched_folder_id="wf-1",
        relative_path="duplicate.jpg",
        detections=[
            {
                "face_id": "face-from-payload",
                "bbox_x": 11,
                "bbox_y": 22,
                "bbox_w": 33,
                "bbox_h": 44,
                "bitmap": b"face-bitmap",
                "embedding": None,
                "provenance": {"detector": "staged"},
            }
        ],
        warnings=[],
    )
    queue_store.enqueue(
        payload_type="extracted_photo",
        payload=extracted_payload,
        idempotency_key="extracted:photo-new-path",
    )

    result = process_pending_ingest_queue(
        database_url,
        limit=10,
        face_detector=RaisingFaceDetector("should not run"),
    )

    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    photo = load_photo_row(database_url, "photo-existing")
    assert photo["photo_id"] == "photo-existing"
    assert photo["path"] == "/library/duplicate.jpg"
    file_rows = load_photo_file_rows(database_url, "photo-existing")
    assert [row["relative_path"] for row in file_rows] == ["duplicate.jpg"]


def test_process_pending_rows_marks_detection_complete_when_no_faces_found(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-no-faces.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-without-faces",
    )

    result = process_pending_ingest_queue(
        database_url,
        limit=10,
        face_detector=StaticFaceDetector(detections=[]),
    )

    assert result.processed == 1
    assert load_face_rows(database_url, SAMPLE_PAYLOAD["photo_id"]) == []
    faces_count, faces_detected_ts = load_photo_detection_state(
        database_url, SAMPLE_PAYLOAD["photo_id"]
    )
    assert faces_count == 0
    assert faces_detected_ts is not None
    completed_rows = queue_store.list_by_status("completed")
    assert len(completed_rows) == 1
    assert completed_rows[0].last_error is None


def test_process_pending_rows_marks_missing_candidate_files_failed(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-ingest-candidate-missing-file.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    missing_path = tmp_path / "missing.jpg"
    candidate_payload = {
        "payload_version": 1,
        "storage_source_id": "source-1",
        "watched_folder_id": "wf-1",
        "canonical_path": "/library/missing.jpg",
        "runtime_path": str(missing_path.resolve()),
        "relative_path": "missing.jpg",
        "filesize": 123,
        "modified_ts": "2024-01-02T00:00:00+00:00",
        "modified_mtime_ns": 123456789,
        "idempotency_key": "wf-1:missing.jpg:123:123456789",
    }
    queue_id = queue_store.enqueue(
        payload_type="ingest_candidate",
        payload=candidate_payload,
        idempotency_key=candidate_payload["idempotency_key"],
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    failed_rows = queue_store.list_by_status("failed")
    file_rows = load_ingest_run_files(database_url)
    assert result.processed == 0
    assert result.failed == 1
    assert result.retryable_errors == 0
    assert len(failed_rows) == 1
    assert failed_rows[0].ingest_queue_id == queue_id
    assert "candidate file missing" in failed_rows[0].last_error.lower()
    assert len(file_rows) == 1
    assert file_rows[0]["path"] == candidate_payload["canonical_path"]
    assert file_rows[0]["outcome"] == "failed"
    assert "candidate file missing" in file_rows[0]["error_detail"].lower()


def test_process_pending_rows_preserves_existing_thumbnail_when_queue_payload_has_no_thumbnail_data(
    tmp_path,
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-preserve-thumbnail.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)
    now = datetime.now(tz=UTC)

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            photos.insert().values(
                photo_id=SAMPLE_PAYLOAD["photo_id"],
                path=SAMPLE_PAYLOAD["path"],
                sha256=SAMPLE_PAYLOAD["sha256"],
                phash=None,
                filesize=999,
                ext=SAMPLE_PAYLOAD["ext"],
                created_ts=now,
                modified_ts=now,
                shot_ts=None,
                shot_ts_source=None,
                camera_make=None,
                camera_model=None,
                software=None,
                orientation=None,
                gps_latitude=None,
                gps_longitude=None,
                gps_altitude=None,
                thumbnail_jpeg=b"existing-thumbnail",
                thumbnail_mime_type="image/jpeg",
                thumbnail_width=64,
                thumbnail_height=48,
                updated_ts=now,
                faces_count=0,
                faces_detected_ts=None,
            )
        )

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=build_payload(filesize=456, modified_ts="2024-01-03T00:00:00+00:00"),
        idempotency_key="photo-preserve-thumbnail",
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    assert result.processed == 1
    photo_row = load_photo_row(database_url, SAMPLE_PAYLOAD["photo_id"])
    assert photo_row["filesize"] == 456
    assert photo_row["thumbnail_jpeg"] == b"existing-thumbnail"
    assert photo_row["thumbnail_mime_type"] == "image/jpeg"
    assert photo_row["thumbnail_width"] == 64
    assert photo_row["thumbnail_height"] == 48


def test_process_pending_rows_keeps_photo_ingest_successful_when_detection_fails(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-face-failure.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-face-failure",
    )

    result = process_pending_ingest_queue(
        database_url,
        limit=10,
        face_detector=RaisingFaceDetector("detector exploded"),
    )

    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert load_photo_paths(database_url) == [SAMPLE_PAYLOAD["path"]]
    assert load_face_rows(database_url, SAMPLE_PAYLOAD["photo_id"]) == []
    faces_count, faces_detected_ts = load_photo_detection_state(
        database_url, SAMPLE_PAYLOAD["photo_id"]
    )
    assert faces_count == 0
    assert faces_detected_ts is None
    completed_rows = queue_store.list_by_status("completed")
    assert len(completed_rows) == 1
    assert "face detection failed" in completed_rows[0].last_error.lower()
    assert "detector exploded" in completed_rows[0].last_error


def test_process_pending_rows_keeps_transient_domain_write_failures_retryable(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-transient.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-transient",
    )

    original_upsert = ingest_queue_processor.upsert_photo

    def flaky_upsert(*args, **kwargs):
        raise RuntimeError("transient db outage")

    monkeypatch.setattr(ingest_queue_processor, "upsert_photo", flaky_upsert)

    first = process_pending_ingest_queue(database_url, limit=10)
    assert first.processed == 0
    assert first.failed == 0
    assert first.retryable_errors == 1
    assert queue_store.list_by_status("failed") == []
    processing_rows = queue_store.list_by_status("processing")
    assert len(processing_rows) == 1
    assert processing_rows[0].attempt_count == 1
    assert processing_rows[0].last_attempt_ts is not None
    assert "transient db outage" in processing_rows[0].last_error

    second = process_pending_ingest_queue(database_url, limit=10)
    assert second.processed == 0
    assert second.failed == 0
    assert second.retryable_errors == 0

    mark_queue_row_processing(
        database_url,
        processing_rows[0].ingest_queue_id,
        last_attempt_ts=datetime.now(tz=UTC)
        - timedelta(seconds=PROCESSING_LEASE_SECONDS + 1),
    )

    monkeypatch.setattr(ingest_queue_processor, "upsert_photo", original_upsert)

    third = process_pending_ingest_queue(database_url, limit=10)

    assert third.processed == 1
    assert third.failed == 0
    assert third.retryable_errors == 0


def test_process_pending_rows_marks_deterministic_domain_write_failures_failed(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-integrity.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    seed_existing_photo_with_same_photo_id(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-integrity",
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    assert result.processed == 0
    assert result.failed == 1
    assert result.retryable_errors == 0
    assert queue_store.list_by_status("processing") == []
    failed_rows = queue_store.list_by_status("failed")
    assert len(failed_rows) == 1
    assert failed_rows[0].attempt_count == 1
    assert "integrity" in failed_rows[0].last_error.lower() or "unique" in failed_rows[0].last_error.lower()


def test_process_pending_rows_retries_rows_left_in_processing_after_retryable_failure(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-reclaim.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)
    queue_id = queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-reclaim",
    )

    original_upsert = ingest_queue_processor.upsert_photo

    def flaky_upsert(*args, **kwargs):
        raise RuntimeError("retry me")

    monkeypatch.setattr(ingest_queue_processor, "upsert_photo", flaky_upsert)

    first = process_pending_ingest_queue(database_url, limit=10)

    processing_rows = queue_store.list_by_status("processing")
    assert first.processed == 0
    assert first.failed == 0
    assert first.retryable_errors == 1
    assert len(processing_rows) == 1
    assert processing_rows[0].ingest_queue_id == queue_id
    assert processing_rows[0].attempt_count == 1

    mark_queue_row_processing(
        database_url,
        queue_id,
        last_attempt_ts=datetime.now(tz=UTC)
        - timedelta(seconds=PROCESSING_LEASE_SECONDS + 1),
    )

    monkeypatch.setattr(ingest_queue_processor, "upsert_photo", original_upsert)

    result = process_pending_ingest_queue(database_url, limit=10)

    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert load_photo_paths(database_url) == [SAMPLE_PAYLOAD["path"]]
    assert queue_store.list_by_status("processing") == []
    assert len(queue_store.list_by_status("completed")) == 1


def test_process_pending_rows_does_not_reclaim_actively_leased_processing_rows(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-active-lease.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)
    queue_id = queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-active-lease",
    )

    mark_queue_row_processing(
        database_url,
        queue_id,
        last_attempt_ts=datetime.now(tz=UTC),
    )

    result = process_pending_ingest_queue(database_url, limit=10)
    processing_rows = queue_store.list_by_status("processing")

    assert result.processed == 0
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert load_photo_paths(database_url) == []
    assert len(processing_rows) == 1
    assert processing_rows[0].ingest_queue_id == queue_id
    assert load_ingest_runs(database_url) == []
    assert load_ingest_run_files(database_url) == []


def test_process_pending_rows_does_not_create_run_when_every_claim_is_lost(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-claim-race.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_id = queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-claim-race",
    )

    def never_claim(*args, **kwargs):
        return None

    monkeypatch.setattr(IngestQueueStore, "begin_processing_attempt", never_claim)

    result = process_pending_ingest_queue(database_url, limit=10)

    assert result == ingest_queue_processor.ProcessQueueResult()
    assert queue_store.list_by_status("pending")[0].ingest_queue_id == queue_id
    assert load_ingest_runs(database_url) == []
    assert load_ingest_run_files(database_url) == []


def test_process_pending_rows_reclaims_processing_rows_only_after_lease_expires(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-stale-lease.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)
    queue_id = queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-stale-lease",
    )

    mark_queue_row_processing(
        database_url,
        queue_id,
        last_attempt_ts=datetime.now(tz=UTC)
        - timedelta(seconds=PROCESSING_LEASE_SECONDS + 1),
    )

    result = process_pending_ingest_queue(database_url, limit=10)

    assert result.processed == 1
    assert result.failed == 0
    assert result.retryable_errors == 0
    assert load_photo_paths(database_url) == [SAMPLE_PAYLOAD["path"]]


def test_process_pending_rows_keeps_row_retryable_when_completion_transition_fails(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'queue-processor-completion-failure.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)

    queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="photo-completion-failure",
    )

    original_execute = Connection.execute

    def flaky_execute(self, statement, *args, **kwargs):
        values = getattr(statement, "_values", {})
        if getattr(statement, "table", None) is ingest_queue and any(
            (getattr(column, "name", column) == "status")
            and getattr(value, "value", value) == "completed"
            for column, value in values.items()
        ):
            raise RuntimeError("queue completion update failed")
        return original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(Connection, "execute", flaky_execute)

    first = process_pending_ingest_queue(database_url, limit=10)

    assert first.retryable_errors == 1

    rows = queue_store.list_by_status("processing")
    assert len(rows) == 1
    assert rows[0].attempt_count == 1

    monkeypatch.setattr(Connection, "execute", original_execute)

    second = process_pending_ingest_queue(database_url, limit=10)

    assert second.processed == 0
    assert second.failed == 0
    assert second.retryable_errors == 0

    mark_queue_row_processing(
        database_url,
        rows[0].ingest_queue_id,
        last_attempt_ts=datetime.now(tz=UTC)
        - timedelta(seconds=PROCESSING_LEASE_SECONDS + 1),
    )

    third = process_pending_ingest_queue(database_url, limit=10)

    assert first.processed == 0
    assert first.failed == 0
    assert first.retryable_errors == 1
    assert third.processed == 1
    assert third.failed == 0
    assert third.retryable_errors == 0
    assert load_photo_paths(database_url) == [SAMPLE_PAYLOAD["path"]]
    assert queue_store.list_by_status("failed") == []
    assert queue_store.list_by_status("processing") == []
    assert len(queue_store.list_by_status("completed")) == 1


class StaticFaceDetector:
    def __init__(self, detections: list[dict]) -> None:
        self._detections = detections

    def detect(self, path):
        return list(self._detections)


class RaisingFaceDetector:
    def __init__(self, message: str) -> None:
        self._message = message

    def detect(self, path):
        raise RuntimeError(self._message)


def test_ingest_run_store_persists_run_lifecycle_and_file_outcomes(tmp_path):
    from app.db import IngestRunFileOutcome, IngestRunStore

    database_url = f"sqlite:///{tmp_path / 'ingest-run-store.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)
    run_store = IngestRunStore(database_url)

    queue_id = queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="ingest-run-store",
    )

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        ingest_run_id = run_store.create_run(connection=connection)
        run_store.append_file_outcome(
            ingest_run_id,
            IngestRunFileOutcome(
                ingest_queue_id=queue_id,
                path=SAMPLE_PAYLOAD["path"],
                outcome="completed",
                error_detail="face detection failed: detector exploded",
            ),
            connection=connection,
        )
        run_store.finalize_run(
            ingest_run_id,
            status="completed",
            files_seen=1,
            files_created=1,
            files_updated=0,
            error_count=1,
            error_summary="face detection failed: detector exploded",
            connection=connection,
        )

    run_rows = load_ingest_runs(database_url)
    file_rows = load_ingest_run_files(database_url)

    assert len(run_rows) == 1
    assert run_rows[0]["ingest_run_id"] == ingest_run_id
    assert run_rows[0]["status"] == "completed"
    assert run_rows[0]["completed_ts"] is not None
    assert run_rows[0]["files_seen"] == 1
    assert run_rows[0]["files_created"] == 1
    assert run_rows[0]["files_updated"] == 0
    assert run_rows[0]["files_missing"] == 0
    assert run_rows[0]["error_count"] == 1
    assert run_rows[0]["error_summary"] == "face detection failed: detector exploded"

    assert len(file_rows) == 1
    assert file_rows[0]["ingest_run_id"] == ingest_run_id
    assert file_rows[0]["ingest_queue_id"] == queue_id
    assert file_rows[0]["path"] == SAMPLE_PAYLOAD["path"]
    assert file_rows[0]["outcome"] == "completed"
    assert file_rows[0]["error_detail"] == "face detection failed: detector exploded"
    assert file_rows[0]["created_ts"] is not None


def test_ingest_run_store_is_exported_from_app_db(tmp_path):
    from app.db import IngestRunStore

    database_url = f"sqlite:///{tmp_path / 'ingest-run-store-export.db'}"
    upgrade_database(database_url)

    store = IngestRunStore(database_url)

    assert isinstance(store, IngestRunStore)


def test_ingest_run_store_manages_its_own_persistence_without_explicit_connection(tmp_path):
    from app.db import IngestRunFileOutcome, IngestRunStore

    database_url = f"sqlite:///{tmp_path / 'ingest-run-store-self-managed.db'}"
    upgrade_database(database_url)
    queue_store = IngestQueueStore(database_url)
    run_store = IngestRunStore(database_url)

    queue_id = queue_store.enqueue(
        payload_type="photo_metadata",
        payload=SAMPLE_PAYLOAD,
        idempotency_key="ingest-run-store-self-managed",
    )

    ingest_run_id = run_store.create_run()
    run_store.append_file_outcome(
        ingest_run_id,
        IngestRunFileOutcome(
            ingest_queue_id=queue_id,
            path=SAMPLE_PAYLOAD["path"],
            outcome="failed",
            error_detail="unsupported payload",
        ),
    )
    run_store.finalize_run(
        ingest_run_id,
        status="failed",
        files_seen=1,
        files_created=0,
        files_updated=0,
        error_count=1,
        error_summary="unsupported payload",
    )

    run_rows = load_ingest_runs(database_url)
    file_rows = load_ingest_run_files(database_url)

    assert len(run_rows) == 1
    assert run_rows[0]["ingest_run_id"] == ingest_run_id
    assert run_rows[0]["status"] == "failed"
    assert run_rows[0]["completed_ts"] is not None
    assert run_rows[0]["files_seen"] == 1
    assert run_rows[0]["files_created"] == 0
    assert run_rows[0]["files_updated"] == 0
    assert run_rows[0]["error_count"] == 1
    assert run_rows[0]["error_summary"] == "unsupported payload"

    assert len(file_rows) == 1
    assert file_rows[0]["ingest_run_id"] == ingest_run_id
    assert file_rows[0]["ingest_queue_id"] == queue_id
    assert file_rows[0]["outcome"] == "failed"
    assert file_rows[0]["error_detail"] == "unsupported payload"


def test_ingest_run_store_finalize_run_raises_when_run_is_missing(tmp_path):
    from app.db import IngestRunStore

    database_url = f"sqlite:///{tmp_path / 'ingest-run-store-missing-run.db'}"
    upgrade_database(database_url)
    run_store = IngestRunStore(database_url)

    with pytest.raises(LookupError, match="missing ingest run"):
        run_store.finalize_run(
            "missing-ingest-run-id",
            status="completed",
            files_seen=1,
            files_created=1,
            files_updated=0,
            error_count=0,
            error_summary=None,
        )
