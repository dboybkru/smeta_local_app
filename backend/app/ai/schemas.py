from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --- providers ---
class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    base_url: str = Field(min_length=1, max_length=500)
    auth_style: Literal["bearer", "x_api_key"] = "bearer"
    api_key: str = ""  # write-only
    enabled: bool = True


class ProviderUpdate(BaseModel):
    base_url: str | None = Field(default=None, max_length=500)
    auth_style: Literal["bearer", "x_api_key"] | None = None
    api_key: str | None = None  # None/пусто = не менять ключ
    enabled: bool | None = None


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    auth_style: str
    enabled: bool
    has_key: bool  # вычисляется в роутере, ключ не отдаётся


# --- models (catalog) ---
class ModelUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    input_price: Decimal | None = None
    output_price: Decimal | None = None
    strengths: str | None = None
    enabled: bool | None = None


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    model_id: str
    label: str
    input_price: Decimal | None
    output_price: Decimal | None
    strengths: str
    enabled: bool


# --- purposes ---
class PurposeUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    primary_model_id: int | None = None
    fallback_model_id: int | None = None
    enabled: bool | None = None


class PurposeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    title: str
    description: str
    primary_model_id: int | None
    fallback_model_id: int | None
    enabled: bool


class Recommendation(BaseModel):
    purpose_key: str
    provider: str
    model_id: str
    rationale: str


# --- usage / costs ---
class UsageRow(BaseModel):
    provider_name: str
    model_id: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost_rub: Decimal | None


class UsageSummary(BaseModel):
    total_calls: int
    total_cost_rub: Decimal | None
    by_model: list[UsageRow]
