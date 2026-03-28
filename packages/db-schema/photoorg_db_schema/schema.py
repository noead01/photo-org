from __future__ import annotations

from typing import Any

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.engine import Connection, Engine


EMBEDDING_DIMENSION = 128


try:
    from pgvector.sqlalchemy import Vector
except ModuleNotFoundError:  # pragma: no cover - exercised when pgvector is absent
    Vector = None


metadata = MetaData()


def embedding_column_type(dialect_name: str | None = None) -> Any:
    if dialect_name == "postgresql":
        if Vector is None:
            raise RuntimeError(
                "pgvector is required for PostgreSQL embeddings. Install the 'pgvector' package."
            )
        return Vector(EMBEDDING_DIMENSION)
    return JSON()


photos = Table(
    "photos",
    metadata,
    Column("photo_id", String(36), primary_key=True),
    Column("sha256", String(64), nullable=False, unique=True),
    Column("phash", String),
    Column("shot_ts", TIMESTAMP(timezone=True)),
    Column("shot_ts_source", String),
    Column("camera_make", String),
    Column("camera_model", String),
    Column("software", String),
    Column("orientation", String),
    Column("gps_latitude", Float),
    Column("gps_longitude", Float),
    Column("gps_altitude", Float),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False),
    Column("updated_ts", TIMESTAMP(timezone=True), nullable=False),
    Column("deleted_ts", TIMESTAMP(timezone=True)),
    # Transitional compatibility fields for the current API code path.
    Column("path", Text, unique=True),
    Column("filesize", Integer),
    Column("ext", String),
    Column("modified_ts", TIMESTAMP(timezone=True)),
    Column("faces_count", Integer, nullable=False, server_default=text("0")),
    Column("faces_detected_ts", TIMESTAMP(timezone=True)),
)

watched_folders = Table(
    "watched_folders",
    metadata,
    Column("watched_folder_id", String(36), primary_key=True),
    Column("scan_path", Text, nullable=False, unique=True),
    Column("container_mount_path", Text, nullable=False, unique=True),
    Column("display_name", String),
    Column("is_enabled", Integer, nullable=False, server_default=text("1")),
    Column("availability_state", String, nullable=False, server_default=text("'active'")),
    Column("last_failure_reason", String),
    Column("last_successful_scan_ts", TIMESTAMP(timezone=True)),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

photo_files = Table(
    "photo_files",
    metadata,
    Column("photo_file_id", String(36), primary_key=True),
    Column("photo_id", String(36), ForeignKey("photos.photo_id", ondelete="CASCADE"), nullable=False),
    Column("watched_folder_id", String(36), ForeignKey("watched_folders.watched_folder_id", ondelete="SET NULL")),
    Column("relative_path", Text, nullable=False),
    Column("filename", String, nullable=False),
    Column("extension", String),
    Column("filesize", Integer),
    Column("created_ts", TIMESTAMP(timezone=True)),
    Column("modified_ts", TIMESTAMP(timezone=True)),
    Column("first_seen_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("last_seen_ts", TIMESTAMP(timezone=True)),
    Column("missing_ts", TIMESTAMP(timezone=True)),
    Column("deleted_ts", TIMESTAMP(timezone=True)),
    Column("lifecycle_state", String, nullable=False, server_default=text("'active'")),
    Column("absence_reason", String),
)

faces = Table(
    "faces",
    metadata,
    Column("face_id", String(36), primary_key=True),
    Column("photo_id", String(36), ForeignKey("photos.photo_id", ondelete="CASCADE"), nullable=False),
    Column("person_id", String(36)),
    Column("bbox_x", Integer),
    Column("bbox_y", Integer),
    Column("bbox_w", Integer),
    Column("bbox_h", Integer),
    Column("bitmap", LargeBinary),
    Column("embedding", JSON()),
    Column("detector_name", String),
    Column("detector_version", String),
    Column("provenance", JSON()),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

photo_tags = Table(
    "photo_tags",
    metadata,
    Column("photo_id", String(36), ForeignKey("photos.photo_id", ondelete="CASCADE"), primary_key=True),
    Column("tag", String, primary_key=True),
)

people = Table(
    "people",
    metadata,
    Column("person_id", String(36), primary_key=True),
    Column("display_name", String, nullable=False),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

face_labels = Table(
    "face_labels",
    metadata,
    Column("face_label_id", String(36), primary_key=True),
    Column("face_id", String(36), ForeignKey("faces.face_id", ondelete="CASCADE"), nullable=False),
    Column("person_id", String(36), ForeignKey("people.person_id", ondelete="CASCADE"), nullable=False),
    Column("label_source", String, nullable=False),
    Column("confidence", Float),
    Column("model_version", String),
    Column("provenance", JSON()),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

ingest_runs = Table(
    "ingest_runs",
    metadata,
    Column("ingest_run_id", String(36), primary_key=True),
    Column("watched_folder_id", String(36), ForeignKey("watched_folders.watched_folder_id", ondelete="SET NULL")),
    Column("status", String, nullable=False),
    Column("started_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("completed_ts", TIMESTAMP(timezone=True)),
    Column("files_seen", Integer, nullable=False, server_default=text("0")),
    Column("files_created", Integer, nullable=False, server_default=text("0")),
    Column("files_updated", Integer, nullable=False, server_default=text("0")),
    Column("files_missing", Integer, nullable=False, server_default=text("0")),
    Column("error_count", Integer, nullable=False, server_default=text("0")),
    Column("error_summary", Text),
)

ingest_run_files = Table(
    "ingest_run_files",
    metadata,
    Column("ingest_run_file_id", String(36), primary_key=True),
    Column("ingest_run_id", String(36), ForeignKey("ingest_runs.ingest_run_id", ondelete="CASCADE"), nullable=False),
    Column("ingest_queue_id", String(36), ForeignKey("ingest_queue.ingest_queue_id", ondelete="CASCADE"), nullable=False),
    Column("path", Text, nullable=False),
    Column("outcome", String, nullable=False),
    Column("error_detail", Text),
    Column(
        "created_ts",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ),
)

ingest_queue = Table(
    "ingest_queue",
    metadata,
    Column("ingest_queue_id", String(36), primary_key=True),
    Column("payload_type", String, nullable=False),
    Column("payload_json", JSON, nullable=False),
    Column("idempotency_key", String, nullable=False, unique=True),
    Column("status", String, nullable=False, server_default=text("'pending'")),
    Column("attempt_count", Integer, nullable=False, server_default=text("0")),
    Column(
        "enqueued_ts",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ),
    Column("last_attempt_ts", TIMESTAMP(timezone=True)),
    Column("processed_ts", TIMESTAMP(timezone=True)),
    Column("last_error", Text),
)

Index("idx_photos_shot_ts", photos.c.shot_ts)
Index("idx_photos_sha256", photos.c.sha256)
Index("idx_faces_photo_id", faces.c.photo_id)
Index("idx_photo_files_photo_id", photo_files.c.photo_id)
Index("idx_photo_tags_photo_id", photo_tags.c.photo_id)
Index("idx_face_labels_face_id", face_labels.c.face_id)
Index("idx_face_labels_person_id", face_labels.c.person_id)
Index("idx_ingest_runs_watched_folder_id", ingest_runs.c.watched_folder_id)
Index("idx_ingest_run_files_ingest_run_id", ingest_run_files.c.ingest_run_id)
Index("idx_ingest_run_files_ingest_queue_id", ingest_run_files.c.ingest_queue_id)
Index("idx_ingest_run_files_run_id_outcome", ingest_run_files.c.ingest_run_id, ingest_run_files.c.outcome)
Index("idx_ingest_queue_status_enqueued_ts", ingest_queue.c.status, ingest_queue.c.enqueued_ts)


def configure_embedding_column(bind: Engine | Connection) -> None:
    faces.c.embedding.type = embedding_column_type(bind.dialect.name)
