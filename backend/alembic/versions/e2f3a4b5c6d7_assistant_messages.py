"""assistant messages (история диалога ассистента по смете)

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("estimate_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["estimate_id"], ["estimates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assistant_messages_estimate_id", "assistant_messages", ["estimate_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_messages_estimate_id", table_name="assistant_messages")
    op.drop_table("assistant_messages")
