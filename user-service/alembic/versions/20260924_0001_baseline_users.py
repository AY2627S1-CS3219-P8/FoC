"""Create the existing users table.

Revision ID: 20260924_0001
Revises:
Create Date: 2026-09-24

"""

from alembic import op
import sqlalchemy as sa


revision = "20260924_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial user-account schema on a fresh database."""

    # The application previously created this schema with
    # Base.metadata.create_all(). Treat that schema as the baseline when
    # upgrading an existing database, while still creating it on a fresh one.
    if sa.inspect(op.get_bind()).has_table("users"):
        return

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("nus_student_number", sa.String(length=9), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=254), nullable=False),
        sa.Column("role", sa.String(length=20), server_default=sa.text("'user'"), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
        sa.CheckConstraint(
            "status IN ('active', 'deactivated', 'suspended')",
            name="ck_users_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_nus_student_number", "users", ["nus_student_number"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """Remove the initial user-account schema."""

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_nus_student_number", table_name="users")
    op.drop_table("users")
