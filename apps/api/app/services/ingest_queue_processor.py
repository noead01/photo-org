from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError

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
    processed = 0
    failed = 0
    retryable_errors = 0
    for row in processable_rows:
        try:
            with engine.begin() as connection:
                claimed_row = queue_store.begin_processing_attempt(
                    row.ingest_queue_id,
                    connection=connection,
                )
                if claimed_row is None:
                    continue
                if claimed_row.payload_type != "photo_metadata":
                    queue_store.mark_failed(
                        claimed_row.ingest_queue_id,
                        f"Unsupported payload_type: {claimed_row.payload_type}",
                        connection=connection,
                    )
                    failed += 1
                    continue
                try:
                    record = payload_to_photo_record(claimed_row.payload_json)
                except (KeyError, TypeError, ValueError) as exc:
                    queue_store.mark_failed(
                        claimed_row.ingest_queue_id,
                        str(exc),
                        connection=connection,
                    )
                    failed += 1
                    continue
                upsert_photo(connection, record)
                detection_warning = _apply_face_detection(
                    connection,
                    record,
                    detector,
                )
                queue_store.mark_completed(
                    claimed_row.ingest_queue_id,
                    last_error=detection_warning,
                    connection=connection,
                )
            processed += 1
        except IntegrityError as exc:
            queue_store.record_permanent_failure(row.ingest_queue_id, str(exc))
            failed += 1
        except Exception as exc:
            queue_store.record_retryable_failure(row.ingest_queue_id, str(exc))
            retryable_errors += 1
            continue

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


def _apply_face_detection(connection, record: PhotoRecord, detector) -> str | None:
    try:
        detections = detector.detect(Path(record.path))
    except Exception as exc:
        return f"face detection failed: {exc}"

    store_face_detections(connection, record.photo_id, detections)
    return None
