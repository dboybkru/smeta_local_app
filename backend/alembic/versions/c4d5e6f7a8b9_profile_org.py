"""CompanyProfile: per-org instead of per-user; AI/DaData/Yandex settings → superuser-only

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-15

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add nullable org_id column
    op.add_column(
        "company_profiles",
        sa.Column("org_id", sa.Integer(), nullable=True),
    )

    # 2. Backfill org_id from the owning user's org_id
    op.execute(
        """
        UPDATE company_profiles
        SET org_id = (
            SELECT org_id FROM users WHERE users.id = company_profiles.user_id
        )
        """
    )

    # 3. If multiple profiles map to the same org, keep the lowest id and delete duplicates
    op.execute(
        """
        DELETE FROM company_profiles a
        USING company_profiles b
        WHERE a.org_id = b.org_id AND a.id > b.id
        """
    )

    # 4. Create FK, index, unique constraint on org_id
    op.create_foreign_key(
        "fk_company_profiles_org",
        "company_profiles", "organizations",
        ["org_id"], ["id"],
    )
    op.create_index("ix_company_profiles_org_id", "company_profiles", ["org_id"])
    op.alter_column("company_profiles", "org_id", nullable=False)
    op.create_unique_constraint("uq_company_profiles_org_id", "company_profiles", ["org_id"])

    # 5. Drop the old per-user unique constraint and column
    # PostgreSQL auto-names UniqueConstraint('user_id') without explicit name as:
    # company_profiles_user_id_key
    op.drop_constraint("company_profiles_user_id_key", "company_profiles", type_="unique")
    op.drop_column("company_profiles", "user_id")


def downgrade() -> None:
    # Restore user_id column (nullable — cannot recover data perfectly)
    op.add_column(
        "company_profiles",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        "company_profiles_user_id_key", "company_profiles", ["user_id"]
    )

    # Remove org_id structures
    op.drop_constraint("uq_company_profiles_org_id", "company_profiles", type_="unique")
    op.drop_index("ix_company_profiles_org_id", table_name="company_profiles")
    op.drop_constraint("fk_company_profiles_org", "company_profiles", type_="foreignkey")
    op.drop_column("company_profiles", "org_id")
