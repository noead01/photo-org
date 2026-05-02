from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select

from app.db.session import create_db_engine
from app.processing.ingest import poll_registered_storage_sources
from app.services.ingest_queue_processor import process_pending_ingest_queue
from app.storage import photos


@dataclass(frozen=True)
class TriggerStorageSourcePollingResult:
    scanned: int
    enqueued: int
    inserted: int
    updated: int
    queue_processed: int
    queue_failed: int
    queue_retryable_errors: int
    poll_errors: tuple[str, ...]

    @property
    def error_count(self) -> int:
        return len(self.poll_errors) + self.queue_failed + self.queue_retryable_errors


def _count_photos(database_url: str | Path | None = None) -> int:
    engine = create_db_engine(database_url)
    try:
        with engine.connect() as connection:
            return connection.scalar(select(func.count()).select_from(photos)) or 0
    finally:
        engine.dispose()


def trigger_storage_source_polling(
    *,
    database_url: str | Path | None = None,
    queue_process_limit: int = 100,
) -> TriggerStorageSourcePollingResult:
    initial_photo_count = _count_photos(database_url)
    poll_result = poll_registered_storage_sources(database_url=database_url)

    queue_processed = 0
    queue_failed = 0
    queue_retryable_errors = 0
    while True:
        queue_result = process_pending_ingest_queue(
            database_url=database_url,
            limit=queue_process_limit,
        )
        queue_processed += queue_result.processed
        queue_failed += queue_result.failed
        queue_retryable_errors += queue_result.retryable_errors
        if queue_result.processed == 0:
            break

    inserted = max(0, _count_photos(database_url) - initial_photo_count)
    return TriggerStorageSourcePollingResult(
        scanned=poll_result.scanned,
        enqueued=poll_result.enqueued,
        inserted=inserted,
        updated=poll_result.updated,
        queue_processed=queue_processed,
        queue_failed=queue_failed,
        queue_retryable_errors=queue_retryable_errors,
        poll_errors=tuple(poll_result.errors),
    )
