"""background jobs table

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-14 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'a7b8c9d0e1f2'
down_revision: str | Sequence[str] | None = 'f6a7b8c9d0e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('processed', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('total', sa.Integer(), nullable=True),
        sa.Column('message', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('error', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_jobs_type', 'jobs', ['type'])
    op.create_index('ix_jobs_status', 'jobs', ['status'])


def downgrade() -> None:
    op.drop_index('ix_jobs_status', table_name='jobs')
    op.drop_index('ix_jobs_type', table_name='jobs')
    op.drop_table('jobs')
