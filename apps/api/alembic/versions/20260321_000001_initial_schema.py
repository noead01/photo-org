from __future__ import annotations

from alembic import op
import sqlalchemy as sa

try:
    from pgvector.sqlalchemy import Vector
except ModuleNotFoundError:  # pragma: no cover
    Vector = None


revision = "20260321_000001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIMENSION = 128


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"

    embedding_type = Vector(EMBEDDING_DIMENSION) if is_postgresql and Vector is not None else sa.JSON()

    op.create_table(
        "photos",
        sa.Column("photo_id", sa.String(36), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("phash", sa.String(), nullable=True),
        sa.Column("shot_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("shot_ts_source", sa.String(), nullable=True),
        sa.Column("camera_make", sa.String(), nullable=True),
        sa.Column("camera_model", sa.String(), nullable=True),
        sa.Column("software", sa.String(), nullable=True),
        sa.Column("orientation", sa.String(), nullable=True),
        sa.Column("gps_latitude", sa.Float(), nullable=True),
        sa.Column("gps_longitude", sa.Float(), nullable=True),
        sa.Column("gps_altitude", sa.Float(), nullable=True),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("deleted_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("path", sa.Text(), nullable=True, unique=True),
        sa.Column("filesize", sa.Integer(), nullable=True),
        sa.Column("ext", sa.String(), nullable=True),
        sa.Column("modified_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("faces_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("faces_detected_ts", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_photos_shot_ts", "photos", ["shot_ts"], unique=False)
    op.create_index("idx_photos_sha256", "photos", ["sha256"], unique=False)

    op.create_table(
        "watched_folders",
        sa.Column("watched_folder_id", sa.String(36), primary_key=True),
        sa.Column("root_path", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("is_enabled", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("availability_state", sa.String(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("last_failure_reason", sa.String(), nullable=True),
        sa.Column("last_successful_scan_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "photo_files",
        sa.Column("photo_file_id", sa.String(36), primary_key=True),
        sa.Column("photo_id", sa.String(36), sa.ForeignKey("photos.photo_id", ondelete="CASCADE"), nullable=False),
        sa.Column("watched_folder_id", sa.String(36), sa.ForeignKey("watched_folders.watched_folder_id", ondelete="SET NULL"), nullable=True),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("extension", sa.String(), nullable=True),
        sa.Column("filesize", sa.Integer(), nullable=True),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("modified_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("first_seen_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_seen_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("missing_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("lifecycle_state", sa.String(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("absence_reason", sa.String(), nullable=True),
    )
    op.create_index("idx_photo_files_photo_id", "photo_files", ["photo_id"], unique=False)

    op.create_table(
        "faces",
        sa.Column("face_id", sa.String(36), primary_key=True),
        sa.Column("photo_id", sa.String(36), sa.ForeignKey("photos.photo_id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=True),
        sa.Column("bbox_x", sa.Integer(), nullable=True),
        sa.Column("bbox_y", sa.Integer(), nullable=True),
        sa.Column("bbox_w", sa.Integer(), nullable=True),
        sa.Column("bbox_h", sa.Integer(), nullable=True),
        sa.Column("bitmap", sa.LargeBinary(), nullable=True),
        sa.Column("embedding", embedding_type, nullable=True),
        sa.Column("detector_name", sa.String(), nullable=True),
        sa.Column("detector_version", sa.String(), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=True),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_faces_photo_id", "faces", ["photo_id"], unique=False)

    op.create_table(
        "people",
        sa.Column("person_id", sa.String(36), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "photo_tags",
        sa.Column("photo_id", sa.String(36), sa.ForeignKey("photos.photo_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag", sa.String(), primary_key=True),
    )
    op.create_index("idx_photo_tags_photo_id", "photo_tags", ["photo_id"], unique=False)

    op.create_table(
        "face_labels",
        sa.Column("face_label_id", sa.String(36), primary_key=True),
        sa.Column("face_id", sa.String(36), sa.ForeignKey("faces.face_id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("people.person_id", ondelete="CASCADE"), nullable=False),
        sa.Column("label_source", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=True),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_face_labels_face_id", "face_labels", ["face_id"], unique=False)
    op.create_index("idx_face_labels_person_id", "face_labels", ["person_id"], unique=False)

    op.create_table(
        "ingest_runs",
        sa.Column("ingest_run_id", sa.String(36), primary_key=True),
        sa.Column("watched_folder_id", sa.String(36), sa.ForeignKey("watched_folders.watched_folder_id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("files_seen", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("files_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("files_updated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("files_missing", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_summary", sa.Text(), nullable=True),
    )
    op.create_index("idx_ingest_runs_watched_folder_id", "ingest_runs", ["watched_folder_id"], unique=False)

    op.create_table(
        "ingest_queue",
        sa.Column("ingest_queue_id", sa.String(36), primary_key=True),
        sa.Column("payload_type", sa.String(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False, unique=True),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("enqueued_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_attempt_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("processed_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index("idx_ingest_queue_status_enqueued_ts", "ingest_queue", ["status", "enqueued_ts"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_ingest_queue_status_enqueued_ts", table_name="ingest_queue")
    op.drop_table("ingest_queue")
    op.drop_index("idx_ingest_runs_watched_folder_id", table_name="ingest_runs")
    op.drop_table("ingest_runs")
    op.drop_index("idx_face_labels_person_id", table_name="face_labels")
    op.drop_index("idx_face_labels_face_id", table_name="face_labels")
    op.drop_table("face_labels")
    op.drop_index("idx_photo_tags_photo_id", table_name="photo_tags")
    op.drop_table("photo_tags")
    op.drop_table("people")
    op.drop_index("idx_faces_photo_id", table_name="faces")
    op.drop_table("faces")
    op.drop_index("idx_photo_files_photo_id", table_name="photo_files")
    op.drop_table("photo_files")
    op.drop_table("watched_folders")
    op.drop_index("idx_photos_sha256", table_name="photos")
    op.drop_index("idx_photos_shot_ts", table_name="photos")
    op.drop_table("photos")
