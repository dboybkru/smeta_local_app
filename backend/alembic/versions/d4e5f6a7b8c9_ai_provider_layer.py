"""ai provider layer

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-13 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: str | Sequence[str] | None = 'c3d4e5f6a7b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'ai_providers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=False),
        sa.Column('auth_style', sa.String(length=20), server_default=sa.text("'bearer'"), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'ai_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.String(length=200), nullable=False),
        sa.Column('label', sa.String(length=200), server_default=sa.text("''"), nullable=False),
        sa.Column('input_price', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('output_price', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('strengths', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['ai_providers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'ai_purposes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), server_default=sa.text("''"), nullable=False),
        sa.Column('description', sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column('primary_model_id', sa.Integer(), nullable=True),
        sa.Column('fallback_model_id', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.ForeignKeyConstraint(['primary_model_id'], ['ai_models.id']),
        sa.ForeignKeyConstraint(['fallback_model_id'], ['ai_models.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    purposes = sa.table(
        'ai_purposes',
        sa.column('key', sa.String), sa.column('title', sa.String),
        sa.column('description', sa.Text), sa.column('enabled', sa.Boolean),
    )
    op.bulk_insert(purposes, [
        {'key': 'proposal_generation', 'title': 'Генерация текстов КП',
         'description': 'Маркетинговые блоки коммерческого предложения по смете и профилю.', 'enabled': True},
        {'key': 'estimate_analysis', 'title': 'Анализ сметы',
         'description': 'Подсказки по составу работ/позиций сметы.', 'enabled': True},
        {'key': 'assistant', 'title': 'Интерактивный ассистент',
         'description': 'Диалоговый помощник редактора смет (фаза 5).', 'enabled': True},
        {'key': 'router', 'title': 'Модель-роутер (советник)',
         'description': 'Подбирает оптимальную модель под каждую цель по цена-качество.', 'enabled': True},
    ])


def downgrade() -> None:
    op.drop_table('ai_purposes')
    op.drop_table('ai_models')
    op.drop_table('ai_providers')
