from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Connection

from app.db import IngestRunFileOutcome, IngestRunStore
from app.db.queue import IngestQueueStore, PROCESSING_LEASE_SECONDS
from app.db.session import create_db_engine
from app.processing.faces import OpenCvFaceDetector
from app.processing.ingest_persistence import (
    PhotoRecord,
    deserialize_detections,
    deserialize_photo_record,
    store_face_detections,
    upsert_photo,
    upsert_source_photo,
)
from app.services.file_reconciliation import activate_observed_file
from app.services.ingest_extraction_worker import CandidateFileMissingError, process_candidate_payload
from app.storage import photo_files


@dataclass(frozen=True)
class ProcessQueueResult:
    processed: int = 0
    failed: int = 0
    retryable_errors: int = 0


class ExtractedPayloadStillProcessingError(RuntimeError):
    pass


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
        queue_store.close()
        return result

    engine = create_db_engine(database_url)
    detector = face_detector if face_detector is not None else OpenCvFaceDetector()
    run_store = IngestRunStore(database_url)
    ingest_run_id: str | None = None
    processed = 0
    failed = 0
    retryable_errors = 0
    files_seen = 0
    files_created = 0
    files_updated = 0
    error_messages: list[str] = []
    file_outcomes: list[str] = []

    try:
        for row in processable_rows:
            claimed_row = None
            claimed_path = _file_outcome_path(row)
            run_created_in_transaction = False
            try:
                with engine.begin() as connection:
                    claimed_row = queue_store.begin_processing_attempt(
                        row.ingest_queue_id,
                        connection=connection,
                    )
                    if claimed_row is None:
                        continue
                    files_seen += 1
                    claimed_path = _file_outcome_path(claimed_row)
                    if claimed_row.payload_type not in {
                        "photo_metadata",
                        "ingest_candidate",
                        "extracted_photo",
                    }:
                        error_detail = f"Unsupported payload_type: {claimed_row.payload_type}"
                        ingest_run_id, run_created_in_transaction = _ensure_ingest_run(
                            run_store,
                            ingest_run_id,
                            connection=connection,
                        )
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
                        file_outcomes.append("failed")
                        failed += 1
                        error_messages.append(error_detail)
                        continue
                    try:
                        created, completion_warning = _process_claimed_row(
                            database_url,
                            queue_store,
                            connection,
                            claimed_row,
                            detector=detector,
                        )
                    except (KeyError, TypeError, ValueError, CandidateFileMissingError) as exc:
                        error_detail = str(exc)
                        ingest_run_id, run_created_in_transaction = _ensure_ingest_run(
                            run_store,
                            ingest_run_id,
                            connection=connection,
                        )
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
                        file_outcomes.append("failed")
                        failed += 1
                        error_messages.append(error_detail)
                        continue
                    ingest_run_id, run_created_in_transaction = _ensure_ingest_run(
                        run_store,
                        ingest_run_id,
                        connection=connection,
                    )
                    run_store.append_file_outcome(
                        ingest_run_id,
                        IngestRunFileOutcome(
                            ingest_queue_id=claimed_row.ingest_queue_id,
                            path=_file_outcome_path(claimed_row),
                            outcome="completed",
                            error_detail=completion_warning,
                        ),
                        connection=connection,
                    )
                    queue_store.mark_completed(
                        claimed_row.ingest_queue_id,
                        last_error=completion_warning,
                        connection=connection,
                    )
                    file_outcomes.append("completed")
                    if created is True:
                        files_created += 1
                    elif created is False:
                        files_updated += 1
                    if completion_warning is not None:
                        error_messages.append(completion_warning)
                processed += 1
            except IntegrityError as exc:
                if run_created_in_transaction:
                    ingest_run_id = None
                error_detail = str(exc)
                queue_store.record_permanent_failure(row.ingest_queue_id, error_detail)
                ingest_run_id, _ = _ensure_ingest_run(run_store, ingest_run_id)
                run_store.append_file_outcome(
                    ingest_run_id,
                    IngestRunFileOutcome(
                        ingest_queue_id=row.ingest_queue_id,
                        path=claimed_path,
                        outcome="failed",
                        error_detail=error_detail,
                    ),
                )
                file_outcomes.append("failed")
                failed += 1
                error_messages.append(error_detail)
            except Exception as exc:
                if run_created_in_transaction:
                    ingest_run_id = None
                error_detail = str(exc)
                queue_store.record_retryable_failure(row.ingest_queue_id, error_detail)
                ingest_run_id, _ = _ensure_ingest_run(run_store, ingest_run_id)
                run_store.append_file_outcome(
                    ingest_run_id,
                    IngestRunFileOutcome(
                        ingest_queue_id=row.ingest_queue_id,
                        path=claimed_path,
                        outcome="retryable_error",
                        error_detail=error_detail,
                    ),
                )
                file_outcomes.append("retryable_error")
                retryable_errors += 1
                error_messages.append(error_detail)
                continue

        if ingest_run_id is None:
            return result

        run_store.finalize_run(
            ingest_run_id,
            status=_run_status(file_outcomes),
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
    finally:
        run_store.close()
        queue_store.close()
        engine.dispose()


def payload_to_photo_record(payload: dict) -> PhotoRecord:
    return deserialize_photo_record(payload)


def _payload_path(payload: object) -> str:
    if isinstance(payload, dict):
        path = payload.get("path")
        if isinstance(path, str) and path:
            return path
    return "<unknown>"


def _ensure_ingest_run(
    run_store: IngestRunStore,
    ingest_run_id: str | None,
    *,
    connection: Connection | None = None,
) -> tuple[str, bool]:
    if ingest_run_id is not None:
        return ingest_run_id, False
    return run_store.create_run(connection=connection), True


def _process_claimed_row(
    database_url,
    queue_store: IngestQueueStore,
    connection: Connection,
    claimed_row,
    *,
    detector,
) -> tuple[bool | None, str | None]:
    if claimed_row.payload_type == "ingest_candidate":
        extraction = process_candidate_payload(
            database_url,
            payload=claimed_row.payload_json,
            face_detector=detector,
        )
        enqueue_result = queue_store.enqueue_in_transaction(
            payload_type="extracted_photo",
            payload=extraction.extracted_payload,
            idempotency_key=_extracted_payload_idempotency_key(extraction.extracted_payload),
            connection=connection,
        )
        if not enqueue_result.created:
            refreshed = queue_store.refresh_nonprocessing_in_transaction(
                enqueue_result.ingest_queue_id,
                payload=extraction.extracted_payload,
                connection=connection,
            )
            if not refreshed:
                collided_row = queue_store.get_row_in_transaction(
                    enqueue_result.ingest_queue_id,
                    connection=connection,
                )
                if collided_row is not None and collided_row.status == "processing":
                    raise ExtractedPayloadStillProcessingError(
                        "extracted payload row is currently processing; retry candidate later"
                    )
                raise RuntimeError(
                    "failed to refresh collided extracted payload row"
                )
        return None, _payload_warning_detail(extraction.extracted_payload)

    record = payload_to_photo_record(claimed_row.payload_json)
    if claimed_row.payload_type == "extracted_photo":
        created, photo_id = upsert_source_photo(connection, record)
        record = PhotoRecord(**{**record.__dict__, "photo_id": photo_id})
        _activate_source_backed_file_instance(
            connection,
            payload=claimed_row.payload_json,
            record=record,
        )
        if not _payload_has_warning_prefix(
            claimed_row.payload_json,
            "face detection failed:",
        ):
            store_face_detections(
                connection,
                record.photo_id,
                deserialize_detections(claimed_row.payload_json.get("detections")),
            )
        return created, _payload_warning_detail(claimed_row.payload_json)

    created = upsert_photo(connection, record)
    detection_warning = _apply_face_detection(
        connection,
        record,
        detector,
    )
    return created, detection_warning


def _run_status(file_outcomes: list[str]) -> str:
    if file_outcomes and all(outcome == "completed" for outcome in file_outcomes):
        return "completed"
    if file_outcomes and all(outcome == "failed" for outcome in file_outcomes):
        return "failed"
    return "partial"


def _file_outcome_path(claimed_row) -> str:
    payload_type = getattr(claimed_row, "payload_type", None)
    payload_json = getattr(claimed_row, "payload_json", None)
    if payload_type == "ingest_candidate" and isinstance(payload_json, dict):
        canonical_path = payload_json.get("canonical_path")
        if isinstance(canonical_path, str) and canonical_path:
            return canonical_path
    return _payload_path(payload_json)


def _error_summary(error_messages: list[str]) -> str | None:
    if not error_messages:
        return None
    distinct_messages = _distinct_error_messages(error_messages)
    max_summary_entries = 3
    summary_entries = distinct_messages[:max_summary_entries]
    if len(distinct_messages) > max_summary_entries:
        summary_entries.append(
            f"(+{len(distinct_messages) - max_summary_entries} more distinct errors)"
        )
    return "\n".join(summary_entries)


def _distinct_error_messages(error_messages: list[str]) -> list[str]:
    seen: set[str] = set()
    distinct_messages: list[str] = []
    for error_message in error_messages:
        if error_message in seen:
            continue
        seen.add(error_message)
        distinct_messages.append(error_message)
    return distinct_messages


def _payload_warning_detail(payload: dict) -> str | None:
    warnings = payload.get("warnings")
    if not isinstance(warnings, list):
        return None
    warning_messages = [warning for warning in warnings if isinstance(warning, str) and warning]
    if not warning_messages:
        return None
    return "\n".join(warning_messages)


def _payload_has_warning_prefix(payload: dict, prefix: str) -> bool:
    warnings = payload.get("warnings")
    if not isinstance(warnings, list):
        return False
    return any(
        isinstance(warning, str) and warning.startswith(prefix)
        for warning in warnings
    )


def _extracted_payload_idempotency_key(payload: dict) -> str:
    return f"extracted:{payload['photo_id']}"


def _activate_source_backed_file_instance(
    connection: Connection,
    *,
    payload: dict,
    record: PhotoRecord,
) -> None:
    watched_folder_id = payload.get("watched_folder_id")
    relative_path = payload.get("relative_path")
    if not isinstance(watched_folder_id, str) or not isinstance(relative_path, str):
        return

    existing_created_ts = connection.execute(
        select(photo_files.c.created_ts).where(
            photo_files.c.watched_folder_id == watched_folder_id,
            photo_files.c.relative_path == relative_path,
        )
    ).scalar_one_or_none()
    activate_observed_file(
        connection,
        watched_folder_id=watched_folder_id,
        photo_id=record.photo_id,
        relative_path=relative_path,
        filename=Path(relative_path).name,
        extension=record.ext or None,
        filesize=record.filesize,
        created_ts=existing_created_ts or record.created_ts,
        modified_ts=record.modified_ts,
        now=datetime.now(tz=UTC),
    )


def _apply_face_detection(connection, record: PhotoRecord, detector) -> str | None:
    try:
        detections = detector.detect(Path(record.path))
    except Exception as exc:
        return f"face detection failed: {exc}"

    store_face_detections(connection, record.photo_id, detections)
    return None
