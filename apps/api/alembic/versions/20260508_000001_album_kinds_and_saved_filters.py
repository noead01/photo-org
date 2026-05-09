from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_000001"
down_revision = "20260507_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("albums") as batch_op:
        batch_op.add_column(
            sa.Column(
                "kind",
                sa.String(),
                nullable=False,
                server_default=sa.text("'editable'"),
            )
        )

    op.rename_table("album_items", "editable_album_items")
    op.drop_index("idx_album_items_photo_id", table_name="editable_album_items")
    op.create_index(
        "idx_editable_album_items_photo_id",
        "editable_album_items",
        ["photo_id"],
        unique=False,
    )

    op.create_table(
        "saved_filter_album_rules",
        sa.Column(
            "album_id",
            sa.String(length=36),
            sa.ForeignKey("albums.album_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("filter_json", sa.JSON(), nullable=False),
        sa.Column(
            "updated_ts",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "uq_saved_filter_album_rules_album_id",
        "saved_filter_album_rules",
        ["album_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_saved_filter_album_rules_album_id",
        table_name="saved_filter_album_rules",
    )
    op.drop_table("saved_filter_album_rules")

    op.drop_index(
        "idx_editable_album_items_photo_id",
        table_name="editable_album_items",
    )
    op.create_index(
        "idx_album_items_photo_id",
        "editable_album_items",
        ["photo_id"],
        unique=False,
    )
    op.rename_table("editable_album_items", "album_items")

    with op.batch_alter_table("albums") as batch_op:
        batch_op.drop_column("kind")
