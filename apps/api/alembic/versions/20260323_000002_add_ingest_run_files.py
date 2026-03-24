from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260323_000002"
down_revision = "20260321_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingest_run_files",
        sa.Column("ingest_run_file_id", sa.String(36), primary_key=True),
        sa.Column(
            "ingest_run_id",
            sa.String(36),
            sa.ForeignKey("ingest_runs.ingest_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ingest_queue_id",
            sa.String(36),
            sa.ForeignKey("ingest_queue.ingest_queue_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_ts",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "idx_ingest_run_files_ingest_run_id",
        "ingest_run_files",
        ["ingest_run_id"],
        unique=False,
    )
    op.create_index(
        "idx_ingest_run_files_ingest_queue_id",
        "ingest_run_files",
        ["ingest_queue_id"],
        unique=False,
    )
    op.create_index(
        "idx_ingest_run_files_run_id_outcome",
        "ingest_run_files",
        ["ingest_run_id", "outcome"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_ingest_run_files_run_id_outcome", table_name="ingest_run_files")
    op.drop_index("idx_ingest_run_files_ingest_queue_id", table_name="ingest_run_files")
    op.drop_index("idx_ingest_run_files_ingest_run_id", table_name="ingest_run_files")
    op.drop_table("ingest_run_files")
