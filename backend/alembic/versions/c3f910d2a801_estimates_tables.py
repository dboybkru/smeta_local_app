"""estimates tables

Revision ID: c3f910d2a801
Revises: 4b72ceb2e512
Create Date: 2026-06-12 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3f910d2a801'
down_revision: str | Sequence[str] | None = '4b72ceb2e512'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('default_price_level_id', sa.Integer(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['default_price_level_id'], ['price_levels.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'estimates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('object_name', sa.String(length=500), server_default=sa.text("''"), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column('vat_enabled', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('vat_rate', sa.Numeric(precision=5, scale=2), server_default=sa.text("'20'"), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'estimate_branches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('estimate_id', sa.Integer(), nullable=False),
        sa.Column('parent_branch_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), server_default=sa.text("'Базовая'"), nullable=False),
        sa.ForeignKeyConstraint(['estimate_id'], ['estimates.id']),
        sa.ForeignKeyConstraint(['parent_branch_id'], ['estimate_branches.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'estimate_sections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('markup_percent', sa.Numeric(precision=5, scale=2), server_default=sa.text("'0'"), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['estimate_branches.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'estimate_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=500), server_default=sa.text("''"), nullable=False),
        sa.Column('unit', sa.String(length=50), server_default=sa.text("'шт'"), nullable=False),
        sa.Column('qty', sa.Numeric(precision=12, scale=3), server_default=sa.text("'1'"), nullable=False),
        sa.Column('work_price', sa.Numeric(precision=12, scale=2), server_default=sa.text("'0'"), nullable=False),
        sa.Column('material_price', sa.Numeric(precision=12, scale=2), server_default=sa.text("'0'"), nullable=False),
        sa.Column('purchase_price_snapshot', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['catalog_items.id']),
        sa.ForeignKeyConstraint(['section_id'], ['estimate_sections.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('estimate_lines')
    op.drop_table('estimate_sections')
    op.drop_table('estimate_branches')
    op.drop_table('estimates')
    op.drop_table('clients')
