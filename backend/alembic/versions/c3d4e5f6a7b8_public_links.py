"""public links

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-13 11:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: str | Sequence[str] | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'public_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('estimate_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('level', sa.String(length=20), server_default=sa.text("'full'"), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'watermark_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False
        ),
        sa.Column(
            'watermark_text', sa.String(length=255), server_default=sa.text("''"), nullable=False
        ),
        sa.Column('revoked', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(['estimate_id'], ['estimates.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_public_links_token'), 'public_links', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_public_links_token'), table_name='public_links')
    op.drop_table('public_links')
