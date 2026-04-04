from __future__ import annotations

import importlib
from datetime import datetime
from pathlib import Path
from typing import Protocol

from app.db.queue import IngestQueueStore
from app.processing.ingest_common import IngestResult, iter_photo_files
from app.processing.ingest_persistence import (
    PhotoRecord,
    build_ingest_submission,
    build_photo_record,
    store_face_detections,
    upsert_photo,
    upsert_source_photo,
)
from app.services.thumbnails import generate_thumbnail

ingest_polling_module = importlib.import_module("app.processing.ingest_polling")


class FaceDetector(Protocol):
    def detect(self, path: Path) -> list[dict]:
        """Return face detections for a photo."""


def ingest_directory(
    root: str | Path,
    database_url: str | Path | None = None,
    *,
    face_detector: FaceDetector | None = None,
) -> IngestResult:
    source_root = Path(root).expanduser().resolve()
    result = IngestResult()

    queue_store = IngestQueueStore(database_url)

    for photo_path in iter_photo_files(source_root):
        result.scanned += 1
        try:
            payload = build_ingest_submission(
                photo_path,
                scan_root=source_root,
                path_root=source_root,
            )
            queue_store.enqueue(
                payload_type="photo_metadata",
                payload=payload,
                idempotency_key=payload["idempotency_key"],
            )
            result.enqueued += 1
        except Exception as exc:
            result.errors.append(f"{photo_path}: {exc}")

    return result


def reconcile_directory(
    root: str | Path,
    database_url: str | Path | None = None,
    *,
    now: datetime | None = None,
    missing_file_grace_period_days: int | None = None,
) -> IngestResult:
    source_root = Path(root).expanduser().resolve()
    return ingest_polling_module.reconcile_directory(
        source_root,
        database_url=database_url,
        now=now,
        missing_file_grace_period_days=missing_file_grace_period_days,
    )


def poll_registered_storage_sources(
    database_url: str | Path | None = None,
    *,
    now: datetime | None = None,
    missing_file_grace_period_days: int | None = None,
    poll_chunk_size: int = 100,
) -> IngestResult:
    return ingest_polling_module.poll_registered_storage_sources(
        database_url=database_url,
        now=now,
        missing_file_grace_period_days=missing_file_grace_period_days,
        poll_chunk_size=poll_chunk_size,
    )
