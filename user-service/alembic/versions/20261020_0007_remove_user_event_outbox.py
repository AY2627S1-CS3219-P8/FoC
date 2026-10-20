"""Retire the unconsumed User account-creation outbox.

Revision ID: 20261020_0007
Revises: 20261017_0006
Create Date: 2026-10-20

"""

import sqlalchemy as sa
from alembic import op


revision = "20261020_0007"
down_revision = "20261017_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_user_outbox_unpublished", table_name="user_outbox_events")
    op.drop_table("user_outbox_events")


def downgrade() -> None:
    op.create_table(
        "user_outbox_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_user_outbox_event_id"),
    )
    op.create_index(
        "ix_user_outbox_unpublished",
        "user_outbox_events",
        ["id"],
        postgresql_where=sa.text("published_at IS NULL"),
    )
