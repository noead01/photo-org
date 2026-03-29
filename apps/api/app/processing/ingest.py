from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Protocol

from app.db.queue import IngestQueueStore
from app.processing.ingest_persistence import (
    PhotoRecord,
    build_ingest_submission,
    build_photo_record,
    store_face_detections,
    upsert_photo,
    upsert_source_photo,
)
from app.services.thumbnails import generate_thumbnail


SUPPORTED_EXTENSIONS = {".heic", ".heif", ".jpeg", ".jpg", ".png"}


class FaceDetector(Protocol):
    def detect(self, path: Path) -> list[dict]:
        """Return face detections for a photo."""


@dataclass
class IngestResult:
    scanned: int = 0
    enqueued: int = 0
    inserted: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)


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
    from app.processing.ingest_polling import reconcile_directory as reconcile_directory_impl

    return reconcile_directory_impl(
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
) -> IngestResult:
    from app.processing.ingest_polling import (
        poll_registered_storage_sources as poll_registered_storage_sources_impl,
    )

    return poll_registered_storage_sources_impl(
        database_url=database_url,
        now=now,
        missing_file_grace_period_days=missing_file_grace_period_days,
    )


def iter_photo_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path
