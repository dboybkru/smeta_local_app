"""catalog characteristics_raw

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-14 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'c9d0e1f2a3b4'
down_revision: str | Sequence[str] | None = 'b8c9d0e1f2a3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('catalog_items', sa.Column('characteristics_raw', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('catalog_items', 'characteristics_raw')
