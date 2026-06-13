from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AIProvider(Base):
    __tablename__ = "ai_providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    base_url: Mapped[str] = mapped_column(String(500))
    auth_style: Mapped[str] = mapped_column(String(20), default="bearer")  # bearer | x_api_key
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AIModel(Base):
    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("provider_id", "model_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("ai_providers.id"))
    model_id: Mapped[str] = mapped_column(String(200))
    label: Mapped[str] = mapped_column(String(200), default="")
    input_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    output_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    strengths: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AIPurpose(Base):
    __tablename__ = "ai_purposes"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    primary_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_models.id"), nullable=True
    )
    fallback_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_models.id"), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AIUsage(Base):
    """Журнал AI-вызовов: фактический расход (токены/стоимость) для контроля затрат.
    Провайдер/модель хранятся строками — история не зависит от жизни провайдера."""

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(50), default="")
    model_id: Mapped[str] = mapped_column(String(200), default="")
    purpose: Mapped[str] = mapped_column(String(50), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_rub: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
