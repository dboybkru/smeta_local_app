from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.types import JSONType


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), unique=True, index=True)
    org_name: Mapped[str] = mapped_column(String(500), default="")
    inn: Mapped[str] = mapped_column(String(20), default="")
    # contacts: {"phone","email","address","site"}
    contacts: Mapped[dict] = mapped_column(JSONType, default=dict)
    bank_requisites: Mapped[str] = mapped_column(Text, default="")
    utp: Mapped[list] = mapped_column(JSONType, default=list)
    cases: Mapped[list] = mapped_column(JSONType, default=list)
    guarantee: Mapped[str] = mapped_column(Text, default="")
    logo_url: Mapped[str] = mapped_column(String(1000), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
