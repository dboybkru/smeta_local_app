"""company profiles

Revision ID: a1b2c3d4e5f6
Revises: c3f910d2a801
Create Date: 2026-06-13 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = 'c3f910d2a801'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'company_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('org_name', sa.String(length=500), server_default=sa.text("''"), nullable=False),
        sa.Column('inn', sa.String(length=20), server_default=sa.text("''"), nullable=False),
        sa.Column('contacts', postgresql.JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('bank_requisites', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('utp', postgresql.JSONB(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('cases', postgresql.JSONB(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('guarantee', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('logo_url', sa.String(length=1000), server_default=sa.text("''"), nullable=False),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )


def downgrade() -> None:
    op.drop_table('company_profiles')
