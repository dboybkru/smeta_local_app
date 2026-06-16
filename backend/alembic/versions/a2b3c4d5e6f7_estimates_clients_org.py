"""estimates + clients: add org_id FK

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-15
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for t in ("clients", "estimates"):
        op.add_column(t, sa.Column("org_id", sa.Integer(), nullable=True))
        op.execute(f"UPDATE {t} SET org_id = (SELECT min(id) FROM organizations)")
        op.alter_column(t, "org_id", nullable=False)
        op.create_foreign_key(f"fk_{t}_org", t, "organizations", ["org_id"], ["id"])
        op.create_index(f"ix_{t}_org_id", t, ["org_id"])


def downgrade() -> None:
    for t in ("estimates", "clients"):
        op.drop_index(f"ix_{t}_org_id", table_name=t)
        op.drop_constraint(f"fk_{t}_org", t, type_="foreignkey")
        op.drop_column(t, "org_id")
