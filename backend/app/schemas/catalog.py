from pydantic import BaseModel, ConfigDict, Field


class ProductListItem(BaseModel):
    id: int
    item_code: str
    name: str


class StoreListItem(BaseModel):
    id: int
    store_code: str
    name: str


class CatalogPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=500)
    total_records: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    items: list[ProductListItem]


class StorePage(CatalogPage):
    items: list[StoreListItem]
