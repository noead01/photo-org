from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from app.db import IngestRunFileOutcome, IngestRunStore
from app.db.queue import IngestQueueStore, PROCESSING_LEASE_SECONDS
from app.db.session import create_db_engine
from app.processing.faces import OpenCvFaceDetector
from app.processing.ingest import PhotoRecord, store_face_detections, upsert_photo


@dataclass(frozen=True)
class ProcessQueueResult:
    processed: int = 0
    failed: int = 0
    retryable_errors: int = 0


def process_pending_ingest_queue(
    database_url: str | Path | None = None,
    *,
    limit: int = 100,
    face_detector=None,
) -> ProcessQueueResult:
    queue_store = IngestQueueStore(database_url)
    processable_rows = queue_store.list_processable(limit=limit)
    result = ProcessQueueResult()

    if not processable_rows:
        return result

    engine = create_db_engine(database_url)
    detector = face_detector if face_detector is not None else OpenCvFaceDetector()
    run_store = IngestRunStore(database_url)
    ingest_run_id = run_store.create_run()
    processed = 0
    failed = 0
    retryable_errors = 0
    files_seen = 0
    files_created = 0
    files_updated = 0
    error_messages: list[str] = []
    for row in processable_rows:
        claimed_row = None
        claimed_path = _payload_path(row.payload_json)
        try:
            with engine.begin() as connection:
                claimed_row = queue_store.begin_processing_attempt(
                    row.ingest_queue_id,
                    connection=connection,
                )
                if claimed_row is None:
                    continue
                files_seen += 1
                claimed_path = _payload_path(claimed_row.payload_json)
                if claimed_row.payload_type != "photo_metadata":
                    error_detail = f"Unsupported payload_type: {claimed_row.payload_type}"
                    run_store.append_file_outcome(
                        ingest_run_id,
                        IngestRunFileOutcome(
                            ingest_queue_id=claimed_row.ingest_queue_id,
                            path=claimed_path,
                            outcome="failed",
                            error_detail=error_detail,
                        ),
                        connection=connection,
                    )
                    queue_store.mark_failed(
                        claimed_row.ingest_queue_id,
                        error_detail,
                        connection=connection,
                    )
                    failed += 1
                    error_messages.append(error_detail)
                    continue
                try:
                    record = payload_to_photo_record(claimed_row.payload_json)
                except (KeyError, TypeError, ValueError) as exc:
                    error_detail = str(exc)
                    run_store.append_file_outcome(
                        ingest_run_id,
                        IngestRunFileOutcome(
                            ingest_queue_id=claimed_row.ingest_queue_id,
                            path=claimed_path,
                            outcome="failed",
                            error_detail=error_detail,
                        ),
                        connection=connection,
                    )
                    queue_store.mark_failed(
                        claimed_row.ingest_queue_id,
                        error_detail,
                        connection=connection,
                    )
                    failed += 1
                    error_messages.append(error_detail)
                    continue
                created = upsert_photo(connection, record)
                detection_warning = _apply_face_detection(
                    connection,
                    record,
                    detector,
                )
                run_store.append_file_outcome(
                    ingest_run_id,
                    IngestRunFileOutcome(
                        ingest_queue_id=claimed_row.ingest_queue_id,
                        path=record.path,
                        outcome="completed",
                        error_detail=detection_warning,
                    ),
                    connection=connection,
                )
                queue_store.mark_completed(
                    claimed_row.ingest_queue_id,
                    last_error=detection_warning,
                    connection=connection,
                )
                if created:
                    files_created += 1
                else:
                    files_updated += 1
                if detection_warning is not None:
                    error_messages.append(detection_warning)
            processed += 1
        except IntegrityError as exc:
            error_detail = str(exc)
            queue_store.record_permanent_failure(row.ingest_queue_id, error_detail)
            run_store.append_file_outcome(
                ingest_run_id,
                IngestRunFileOutcome(
                    ingest_queue_id=row.ingest_queue_id,
                    path=claimed_path,
                    outcome="failed",
                    error_detail=error_detail,
                ),
            )
            failed += 1
            error_messages.append(error_detail)
        except Exception as exc:
            error_detail = str(exc)
            queue_store.record_retryable_failure(row.ingest_queue_id, error_detail)
            run_store.append_file_outcome(
                ingest_run_id,
                IngestRunFileOutcome(
                    ingest_queue_id=row.ingest_queue_id,
                    path=claimed_path,
                    outcome="retryable_error",
                    error_detail=error_detail,
                ),
            )
            retryable_errors += 1
            error_messages.append(error_detail)
            continue

    run_store.finalize_run(
        ingest_run_id,
        status=_run_status(failed=failed, retryable_errors=retryable_errors),
        files_seen=files_seen,
        files_created=files_created,
        files_updated=files_updated,
        error_count=len(error_messages),
        error_summary=_error_summary(error_messages),
    )

    return ProcessQueueResult(
        processed=processed,
        failed=failed,
        retryable_errors=retryable_errors,
    )


def payload_to_photo_record(payload: dict) -> PhotoRecord:
    return PhotoRecord(
        photo_id=payload["photo_id"],
        path=payload["path"],
        sha256=payload["sha256"],
        filesize=payload["filesize"],
        ext=payload["ext"],
        created_ts=datetime.fromisoformat(payload["created_ts"]),
        modified_ts=datetime.fromisoformat(payload["modified_ts"]),
        shot_ts=_parse_optional_timestamp(payload.get("shot_ts")),
        shot_ts_source=payload.get("shot_ts_source"),
        camera_make=payload.get("camera_make"),
        camera_model=payload.get("camera_model"),
        software=payload.get("software"),
        orientation=payload.get("orientation"),
        gps_latitude=payload.get("gps_latitude"),
        gps_longitude=payload.get("gps_longitude"),
        gps_altitude=payload.get("gps_altitude"),
        faces_count=payload.get("faces_count", 0),
    )


def _parse_optional_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _payload_path(payload: object) -> str:
    if isinstance(payload, dict):
        path = payload.get("path")
        if isinstance(path, str) and path:
            return path
    return "<unknown>"


def _run_status(*, failed: int, retryable_errors: int) -> str:
    if failed or retryable_errors:
        return "failed"
    return "completed"


def _error_summary(error_messages: list[str]) -> str | None:
    if not error_messages:
        return None
    return "\n".join(error_messages)


def _apply_face_detection(connection, record: PhotoRecord, detector) -> str | None:
    try:
        detections = detector.detect(Path(record.path))
    except Exception as exc:
        return f"face detection failed: {exc}"

    store_face_detections(connection, record.photo_id, detections)
    return None
