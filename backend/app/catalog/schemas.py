from pydantic import BaseModel, ConfigDict, Field


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
