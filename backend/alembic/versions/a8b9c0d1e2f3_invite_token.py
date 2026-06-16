"""user.invite_token + invite_expires_at

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-06-16
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: str | Sequence[str] | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("invite_token", sa.String(length=64), nullable=True))
    op.add_column(
        "users", sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_users_invite_token", "users", ["invite_token"])


def downgrade() -> None:
    op.drop_index("ix_users_invite_token", table_name="users")
    op.drop_column("users", "invite_expires_at")
    op.drop_column("users", "invite_token")
