"""app_settings + client requisites

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-14 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'b8c9d0e1f2a3'
down_revision: str | Sequence[str] | None = 'a7b8c9d0e1f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLIENT_COLS = [
    "inn", "kpp", "ogrn", "type", "address", "actual_address",
    "phone", "email", "contact_person", "bank_name", "bank_account", "bik",
]


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )
    for col in _CLIENT_COLS:
        op.add_column('clients', sa.Column(col, sa.String(length=500), nullable=True))


def downgrade() -> None:
    for col in reversed(_CLIENT_COLS):
        op.drop_column('clients', col)
    op.drop_table('app_settings')
