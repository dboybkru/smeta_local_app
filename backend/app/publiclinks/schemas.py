from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublicLinkIn(BaseModel):
    level: str = Field(default="full", pattern="^(full|cover|estimate)$")
    expires_at: datetime | None = None
    watermark_enabled: bool = False
    watermark_text: str = Field(default="", max_length=255)


class PublicLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estimate_id: int
    token: str
    level: str
    expires_at: datetime | None
    watermark_enabled: bool
    watermark_text: str
    revoked: bool
    created_at: datetime
