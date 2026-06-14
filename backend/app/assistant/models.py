from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AssistantMessage(Base):
    """История диалога ассистента, привязанная к смете (роль user/assistant)."""

    __tablename__ = "assistant_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_id: Mapped[int] = mapped_column(
        ForeignKey("estimates.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
