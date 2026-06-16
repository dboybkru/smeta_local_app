"""jobs.org_id (FK + NOT NULL, backfill from params)

Revision ID: f7a8b9c0d1e2
Revises: c4d5e6f7a8b9
Create Date: 2026-06-16
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("org_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE jobs SET org_id = (params->>'org_id')::int "
        "WHERE params->>'org_id' IS NOT NULL"
    )
    op.execute(
        "UPDATE jobs SET org_id = (SELECT min(id) FROM organizations) WHERE org_id IS NULL"
    )
    op.alter_column("jobs", "org_id", nullable=False)
    op.create_foreign_key("fk_jobs_org", "jobs", "organizations", ["org_id"], ["id"])
    op.create_index("ix_jobs_org_id", "jobs", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_org_id", table_name="jobs")
    op.drop_constraint("fk_jobs_org", "jobs", type_="foreignkey")
    op.drop_column("jobs", "org_id")
