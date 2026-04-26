from __future__ import annotations

from alembic import op


revision = "20260426_000002"
down_revision = "20260321_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("faces", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_faces_person_id_people",
            "people",
            ["person_id"],
            ["person_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("faces", schema=None) as batch_op:
        batch_op.drop_constraint("fk_faces_person_id_people", type_="foreignkey")
