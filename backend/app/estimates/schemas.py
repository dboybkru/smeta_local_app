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


# --- estimates ---
class EstimateIn(BaseModel):
    object_name: str = Field(default="", max_length=500)
    client_id: int | None = None
    vat_enabled: bool = False
    vat_rate: Decimal = Decimal("20")


class EstimatePatch(BaseModel):
    object_name: str | None = Field(default=None, max_length=500)
    status: str | None = None
    client_id: int | None = None
    vat_enabled: bool | None = None
    vat_rate: Decimal | None = None


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_branch_id: int | None


class EstimateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int | None
    owner_id: int
    object_name: str
    status: str
    vat_enabled: bool
    vat_rate: Decimal
    branches: list[BranchOut]


# --- sections ---
class SectionIn(BaseModel):
    name: str = Field(default="", max_length=255)
    markup_percent: Decimal = Decimal("0")


class SectionPatch(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    sort_order: int | None = None
    markup_percent: Decimal | None = None


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_id: int
    name: str
    sort_order: int
    markup_percent: Decimal
