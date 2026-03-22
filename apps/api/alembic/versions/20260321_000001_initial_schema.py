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

    if is_postgresql:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    embedding_type = Vector(EMBEDDING_DIMENSION) if is_postgresql and Vector is not None else sa.JSON()

    op.create_table(
        "photos",
        sa.Column("photo_id", sa.String(), primary_key=True),
        sa.Column("path", sa.Text(), nullable=False, unique=True),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("phash", sa.String(), nullable=True),
        sa.Column("filesize", sa.Integer(), nullable=False),
        sa.Column("ext", sa.String(), nullable=False),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("modified_ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("shot_ts", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("shot_ts_source", sa.String(), nullable=True),
        sa.Column("camera_make", sa.String(), nullable=True),
        sa.Column("camera_model", sa.String(), nullable=True),
        sa.Column("software", sa.String(), nullable=True),
        sa.Column("orientation", sa.String(), nullable=True),
        sa.Column("gps_latitude", sa.Float(), nullable=True),
        sa.Column("gps_longitude", sa.Float(), nullable=True),
        sa.Column("gps_altitude", sa.Float(), nullable=True),
        sa.Column("faces_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("faces_detected_ts", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_photos_shot_ts", "photos", ["shot_ts"], unique=False)
    op.create_index("idx_photos_sha256", "photos", ["sha256"], unique=False)

    op.create_table(
        "faces",
        sa.Column("face_id", sa.String(), primary_key=True),
        sa.Column("photo_id", sa.String(), sa.ForeignKey("photos.photo_id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.String(), nullable=True),
        sa.Column("bbox_x", sa.Integer(), nullable=True),
        sa.Column("bbox_y", sa.Integer(), nullable=True),
        sa.Column("bbox_w", sa.Integer(), nullable=True),
        sa.Column("bbox_h", sa.Integer(), nullable=True),
        sa.Column("bitmap", sa.LargeBinary(), nullable=True),
        sa.Column("embedding", embedding_type, nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=True),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_faces_photo_id", "faces", ["photo_id"], unique=False)

    op.create_table(
        "people",
        sa.Column("person_id", sa.String(), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "photo_tags",
        sa.Column("photo_id", sa.String(), sa.ForeignKey("photos.photo_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag", sa.String(), primary_key=True),
    )
    op.create_index("idx_photo_tags_photo_id", "photo_tags", ["photo_id"], unique=False)

    op.create_table(
        "face_labels",
        sa.Column("face_id", sa.String(), sa.ForeignKey("faces.face_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("person_id", sa.String(), sa.ForeignKey("people.person_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("label_source", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("face_labels")
    op.drop_index("idx_photo_tags_photo_id", table_name="photo_tags")
    op.drop_table("photo_tags")
    op.drop_table("people")
    op.drop_index("idx_faces_photo_id", table_name="faces")
    op.drop_table("faces")
    op.drop_index("idx_photos_sha256", table_name="photos")
    op.drop_index("idx_photos_shot_ts", table_name="photos")
    op.drop_table("photos")
