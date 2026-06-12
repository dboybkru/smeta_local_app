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
