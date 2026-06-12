from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    default_price_level_id: Mapped[int | None] = mapped_column(
        ForeignKey("price_levels.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Estimate(Base):
    __tablename__ = "estimates"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    object_name: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    vat_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("20"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    branches: Mapped[list["EstimateBranch"]] = relationship(
        back_populates="estimate", cascade="all, delete-orphan"
    )


class EstimateBranch(Base):
    __tablename__ = "estimate_branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_id: Mapped[int] = mapped_column(ForeignKey("estimates.id"))
    parent_branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("estimate_branches.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), default="Базовая")

    estimate: Mapped["Estimate"] = relationship(back_populates="branches")
    sections: Mapped[list["EstimateSection"]] = relationship(
        back_populates="branch", cascade="all, delete-orphan"
    )


class EstimateSection(Base):
    __tablename__ = "estimate_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("estimate_branches.id"))
    name: Mapped[str] = mapped_column(String(255), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    markup_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))

    branch: Mapped["EstimateBranch"] = relationship(back_populates="sections")
    lines: Mapped[list["EstimateLine"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )


class EstimateLine(Base):
    __tablename__ = "estimate_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("estimate_sections.id"))
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_items.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(500), default="")
    unit: Mapped[str] = mapped_column(String(50), default="шт")
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("1"))
    work_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    material_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    purchase_price_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    section: Mapped["EstimateSection"] = relationship(back_populates="lines")
