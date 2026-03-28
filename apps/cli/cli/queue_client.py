from __future__ import annotations

from pathlib import Path

from app.dev.seed_corpus import load_seed_corpus_into_database
from app.processing.ingest import FaceDetector, IngestResult, ingest_directory


def enqueue_directory(
    root: str | Path,
    *,
    database_url: str | Path | None = None,
    container_mount_path: str | Path | None = None,
    face_detector: FaceDetector | None = None,
) -> IngestResult:
    return ingest_directory(
        root,
        database_url=database_url,
        container_mount_path=container_mount_path,
        face_detector=face_detector,
    )


def load_seed_corpus_into_queue(
    *,
    database_url: str | None = None,
) -> dict[str, int]:
    return load_seed_corpus_into_database(database_url=database_url)
