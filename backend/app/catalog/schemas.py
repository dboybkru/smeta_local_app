from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ColumnMapping(BaseModel):
    """Маппинг колонок файла: индексы колонок; price_cols: {price_level_id: column_index}."""

    name_col: int
    article_col: int | None = None
    unit_col: int | None = None
    category_col: int | None = None
    price_cols: dict[int, int] = Field(default_factory=dict)


class PriceLevelIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0


class PriceLevelPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None


class PriceLevelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int


class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    column_mapping_template: dict | None


class ColumnOut(BaseModel):
    index: int
    header: str
    samples: list[str]


class SheetOut(BaseModel):
    name: str
    row_count: int
    header_row: int
    columns: list[ColumnOut]


class InspectOut(BaseModel):
    sheets: list[SheetOut]


class ImportSummaryOut(BaseModel):
    price_list_id: int
    version: int
    items_created: int
    items_updated: int
    prices_written: int
    price_changes: int
    rows_skipped: int
    problems: list[str] = []


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: int
    name: str
    article: str
    unit: str
    category: str
    kind: str
    prices: dict[int, Decimal] = {}
    characteristics: dict | None = None


class ItemsPageOut(BaseModel):
    items: list[ItemOut]
    total: int


class PriceHistoryOut(BaseModel):
    price_list_id: int
    version: int
    imported_at: str
    price_level_id: int
    value: Decimal


class PriceListOut(BaseModel):
    id: int
    supplier_id: int
    filename: str
    version: int
    imported_at: str | None = None
