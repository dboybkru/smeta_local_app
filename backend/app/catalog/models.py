from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

KINDS = ("material", "work")


class PriceLevel(Base):
    __tablename__ = "price_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    sort_order: Mapped[int] = mapped_column(default=0)


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    column_mapping_template: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )


class PriceList(Base):
    __tablename__ = "price_lists"
    __table_args__ = (
        UniqueConstraint("supplier_id", "version"),
        CheckConstraint("version > 0", name="ck_price_lists_version_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    version: Mapped[int]
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    # article = "" (не NULL) сознательно: UC работает по точному совпадению строк.
    # UC — только guard от точных дублей; upsert-ключ (артикул если есть, иначе имя)
    # реализуется в importer через SELECT, а не через ON CONFLICT.
    __table_args__ = (
        UniqueConstraint("supplier_id", "article", "name"),
        CheckConstraint("kind IN ('material', 'work')", name="ck_catalog_items_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    name: Mapped[str] = mapped_column(String(500), index=True)
    article: Mapped[str] = mapped_column(String(100), default="", index=True)
    unit: Mapped[str] = mapped_column(String(20), default="шт")
    category: Mapped[str] = mapped_column(String(255), default="")
    kind: Mapped[str] = mapped_column(String(10), default="material")
    characteristics: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    characteristics_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price_on_request: Mapped[bool] = mapped_column(Boolean, default=False)


class ItemPrice(Base):
    __tablename__ = "item_prices"
    __table_args__ = (UniqueConstraint("item_id", "price_list_id", "price_level_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id"), index=True)
    price_list_id: Mapped[int] = mapped_column(ForeignKey("price_lists.id"), index=True)
    price_level_id: Mapped[int] = mapped_column(ForeignKey("price_levels.id"), index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
