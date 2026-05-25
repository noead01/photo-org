from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260525_000001"
down_revision = "20260508_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("auth_provider", sa.String(), nullable=False),
        sa.Column("auth_subject", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
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
        sa.UniqueConstraint("auth_subject", name="uq_users_auth_subject"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("idx_users_email", "users", ["email"], unique=False)

    op.create_table(
        "user_role_assignments",
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(), primary_key=True),
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
        sa.CheckConstraint(
            "role IN ('viewer', 'contributor', 'admin')",
            name="ck_user_role_assignments_role",
        ),
    )
    op.create_index(
        "idx_user_role_assignments_role",
        "user_role_assignments",
        ["role"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_user_role_assignments_role",
        table_name="user_role_assignments",
    )
    op.drop_table("user_role_assignments")
    op.drop_index("idx_users_email", table_name="users")
    op.drop_table("users")
