"""catalog: add org_id to catalog domain tables + per-org uniqueness

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-06-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add org_id to catalog tables: suppliers, price_levels, price_lists, catalog_items
    for t in ("suppliers", "price_levels", "price_lists", "catalog_items"):
        op.add_column(t, sa.Column("org_id", sa.Integer(), nullable=True))
        op.execute(f"UPDATE {t} SET org_id = (SELECT min(id) FROM organizations)")
        op.alter_column(t, "org_id", nullable=False)
        op.create_foreign_key(f"fk_{t}_org", t, "organizations", ["org_id"], ["id"])
        op.create_index(f"ix_{t}_org_id", t, ["org_id"])

    # Drop old global unique constraints (PostgreSQL auto-named from original migration).
    # Original migration used sa.UniqueConstraint('name') without an explicit name=,
    # so PostgreSQL generated: <table>_<col>_key  (standard auto-naming pattern).
    #   price_levels → price_levels_name_key
    #   suppliers    → suppliers_name_key
    op.drop_constraint("price_levels_name_key", "price_levels", type_="unique")
    op.create_unique_constraint(
        "uq_price_levels_org_name", "price_levels", ["org_id", "name"]
    )

    op.drop_constraint("suppliers_name_key", "suppliers", type_="unique")
    op.create_unique_constraint(
        "uq_suppliers_org_name", "suppliers", ["org_id", "name"]
    )


def downgrade() -> None:
    # Restore global unique constraints (use original PostgreSQL auto-generated names)
    op.drop_constraint("uq_suppliers_org_name", "suppliers", type_="unique")
    op.create_unique_constraint("suppliers_name_key", "suppliers", ["name"])

    op.drop_constraint("uq_price_levels_org_name", "price_levels", type_="unique")
    op.create_unique_constraint("price_levels_name_key", "price_levels", ["name"])

    # Remove org_id columns
    for t in ("catalog_items", "price_lists", "price_levels", "suppliers"):
        op.drop_index(f"ix_{t}_org_id", table_name=t)
        op.drop_constraint(f"fk_{t}_org", t, type_="foreignkey")
        op.drop_column(t, "org_id")
