"""organizations + user.is_superuser + user.org_id (nullable) + default org

Revision ID: f1a2b3c4d5e6
Revises: e2f3a4b5c6d7
Create Date: 2026-06-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_organizations_name"),
    )
    op.execute(
        "INSERT INTO organizations (name, created_at) VALUES ('Организация', CURRENT_TIMESTAMP)"
    )
    op.add_column("users", sa.Column(
        "is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column(
        "org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True))
    op.create_index("ix_users_org_id", "users", ["org_id"])
    op.execute("UPDATE users SET org_id = (SELECT min(id) FROM organizations)")
    op.execute("UPDATE users SET is_superuser = true WHERE role = 'admin'")
    op.execute("UPDATE users SET role = 'org_admin' WHERE role = 'admin'")


def downgrade() -> None:
    op.drop_index("ix_users_org_id", table_name="users")
    op.drop_column("users", "org_id")
    op.drop_column("users", "is_superuser")
    op.drop_table("organizations")
