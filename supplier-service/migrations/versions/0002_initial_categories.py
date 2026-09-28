"""Seed the controlled categories with permanent, once-generated UUIDs."""

from uuid import UUID

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CATEGORIES = (
    (UUID("90909a88-65cc-4150-8b71-abc339d0c033"), "Food"),
    (UUID("92f0136e-5617-4380-9367-b2991ceda339"), "Coffee"),
    (UUID("e80d50ef-3a8a-43d7-a39e-6a4beb42ea22"), "Shopping"),
    (UUID("419a5b1b-bb4c-4869-a9a3-9b5b1793add2"), "Printing"),
)
category = sa.table("category", sa.column("id", sa.UUID()), sa.column("name", sa.Text()))


def upgrade() -> None:
    op.bulk_insert(category, [{"id": id_, "name": name} for id_, name in CATEGORIES])


def downgrade() -> None:
    # Foreign keys deliberately block removal of categories still in use.
    op.execute(category.delete().where(category.c.id.in_([id_ for id_, _ in CATEGORIES])))
