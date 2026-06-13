from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PublicLink(Base):
    __tablename__ = "public_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_id: Mapped[int] = mapped_column(ForeignKey("estimates.id"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    level: Mapped[str] = mapped_column(String(20), default="full")
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    watermark_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    watermark_text: Mapped[str] = mapped_column(String(255), default="")
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
