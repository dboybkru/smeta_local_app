from decimal import Decimal
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


# --- chat ---
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


# --- операции changeset ---
class AddSection(BaseModel):
    op: Literal["add_section"]
    name: str


class AddCatalogLine(BaseModel):
    op: Literal["add_catalog_line"]
    section_name: str
    catalog_item_id: int
    qty: Decimal = Decimal("1")


class AddCustomLine(BaseModel):
    op: Literal["add_custom_line"]
    section_name: str
    name: str
    unit: str = "шт"
    qty: Decimal = Decimal("1")
    material_price: Decimal = Decimal("0")
    work_price: Decimal = Decimal("0")


class SetQty(BaseModel):
    op: Literal["set_qty"]
    line_id: int
    qty: Decimal


class SetPrice(BaseModel):
    op: Literal["set_price"]
    line_id: int
    material_price: Decimal | None = None
    work_price: Decimal | None = None


class DeleteLine(BaseModel):
    op: Literal["delete_line"]
    line_id: int


class DeleteSection(BaseModel):
    op: Literal["delete_section"]
    section_id: int


class SetSectionMarkup(BaseModel):
    op: Literal["set_section_markup"]
    section_id: int
    markup_percent: Decimal


class SetVat(BaseModel):
    op: Literal["set_vat"]
    vat_enabled: bool
    vat_rate: Decimal | None = None


Operation = Annotated[
    Union[
        AddSection, AddCatalogLine, AddCustomLine, SetQty, SetPrice,
        DeleteLine, DeleteSection, SetSectionMarkup, SetVat,
    ],
    Field(discriminator="op"),
]


class ApplyRequest(BaseModel):
    operations: list[Operation]


class ChatResponse(BaseModel):
    reply: str
    operations: list[Operation]


# --- JSON-схемы для call_llm (встраиваются как текст-подсказка) ---
SEARCH_SCHEMA = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["queries"],
}

CHANGESET_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "operations": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["reply", "operations"],
}
