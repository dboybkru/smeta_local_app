"""ai usage log

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-13 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'e5f6a7b8c9d0'
down_revision: str | Sequence[str] | None = 'd4e5f6a7b8c9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'ai_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_name', sa.String(length=50), server_default=sa.text("''"), nullable=False),
        sa.Column('model_id', sa.String(length=200), server_default=sa.text("''"), nullable=False),
        sa.Column('purpose', sa.String(length=50), server_default=sa.text("''"), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('cost_rub', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('ai_usage')
