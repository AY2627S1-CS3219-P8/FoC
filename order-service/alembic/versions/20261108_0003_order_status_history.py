"""Order status history.

Revision ID: 20261108_0003
Revises: 20261022_0002
Create Date: 2026-11-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261108_0003"
down_revision: Union[str, None] = "20261022_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS_CHECK = (
    "to_status IN ('PENDING_CREDIT', 'OPEN', 'REJECTED', 'ACCEPTED', "
    "'PICKED_UP', 'COMPLETED', 'CANCELLED', 'EXPIRED')"
)


def upgrade() -> None:
    op.create_table(
        "order_status_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(_STATUS_CHECK, name="ck_order_status_history_to_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_status_history_order_id_id",
        "order_status_history",
        ["order_id", "id"],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO order_status_history
                (order_id, from_status, to_status, actor_id, reason, occurred_at)
            SELECT id, NULL, status, NULL, 'backfill', updated_at
            FROM orders
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_order_status_history_order_id_id", table_name="order_status_history"
    )
    op.drop_table("order_status_history")
