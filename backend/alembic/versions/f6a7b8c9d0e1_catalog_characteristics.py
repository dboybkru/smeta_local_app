"""catalog item characteristics + catalog_extract purpose

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-14 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'f6a7b8c9d0e1'
down_revision: str | Sequence[str] | None = 'e5f6a7b8c9d0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('catalog_items', sa.Column('characteristics', sa.JSON(), nullable=True))
    purposes = sa.table(
        'ai_purposes',
        sa.column('key', sa.String), sa.column('title', sa.String),
        sa.column('description', sa.Text), sa.column('enabled', sa.Boolean),
    )
    op.bulk_insert(purposes, [{
        'key': 'catalog_extract',
        'title': 'Извлечение характеристик',
        'description': 'Извлекает характеристики оборудования из названия позиции (ключ-значение).',
        'enabled': True,
    }])


def downgrade() -> None:
    op.execute("DELETE FROM ai_purposes WHERE key = 'catalog_extract'")
    op.drop_column('catalog_items', 'characteristics')
