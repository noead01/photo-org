from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260507_000001"
down_revision = "20260506_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "albums",
        sa.Column("album_id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column(
            "created_ts",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_ts",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "idx_albums_owner_updated_ts",
        "albums",
        ["owner_user_id", "updated_ts"],
        unique=False,
    )

    op.create_table(
        "album_items",
        sa.Column(
            "album_id",
            sa.String(length=36),
            sa.ForeignKey("albums.album_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "photo_id",
            sa.String(length=36),
            sa.ForeignKey("photos.photo_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("added_by_user_id", sa.String(), nullable=False),
        sa.Column(
            "added_ts",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("idx_album_items_photo_id", "album_items", ["photo_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_album_items_photo_id", table_name="album_items")
    op.drop_table("album_items")
    op.drop_index("idx_albums_owner_updated_ts", table_name="albums")
    op.drop_table("albums")
