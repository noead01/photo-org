from __future__ import annotations

from photoorg_db_schema import (
    exif_semantic_mappings,
    exif_semantics,
    face_labels,
    faces,
    ingest_runs,
    ingest_run_files,
    ingest_queue,
    metadata,
    people,
    photo_files,
    photo_exif_attributes,
    photo_tags,
    photos,
    storage_source_aliases,
    storage_sources,
    watched_folders,
)
from app.db.config import DEFAULT_DATABASE_URL, DEFAULT_SQLITE_PATH, resolve_database_url
from app.db.session import create_db_engine, create_session_factory
