from datetime import datetime
from decimal import Decimal  # noqa: F401  — используется в Task 3+

from pydantic import BaseModel, ConfigDict, Field


# --- clients ---
class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    default_price_level_id: int | None = None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    default_price_level_id: int | None
    created_at: datetime
