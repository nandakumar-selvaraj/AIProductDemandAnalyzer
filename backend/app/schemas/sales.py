"""Sales summary response schemas."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class DailySalesSummary(BaseModel):
    sale_date: date
    total_sales: int


class SalesSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None
    end_date: date | None
    total_sales: int
    store_count: int
    product_count: int
    daily_sales: list[DailySalesSummary]
