from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260506_000001"
down_revision = "20260321_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("faces") as batch_op:
        batch_op.add_column(sa.Column("dismissed_ts", sa.TIMESTAMP(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("dismissal_provenance", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("faces") as batch_op:
        batch_op.drop_column("dismissal_provenance")
        batch_op.drop_column("dismissed_ts")
