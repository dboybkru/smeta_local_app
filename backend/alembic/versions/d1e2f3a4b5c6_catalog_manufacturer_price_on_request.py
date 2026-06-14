"""catalog manufacturer + price_on_request

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-06-14

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "catalog_items",
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "catalog_items",
        sa.Column(
            "price_on_request",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("catalog_items", "price_on_request")
    op.drop_column("catalog_items", "manufacturer")
