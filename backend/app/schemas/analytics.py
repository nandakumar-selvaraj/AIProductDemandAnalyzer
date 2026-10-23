from datetime import date

from pydantic import BaseModel, Field


class SalesPoint(BaseModel):
    period: date
    units_sold: int


class ProductAnalyticsResponse(BaseModel):
    product_id: int
    store_id: int | None
    start_date: date | None
    end_date: date | None
    total_units_sold: int
    observed_dates: int = Field(description="Distinct dates with actual sales records")
    daily_sales: list[SalesPoint]
    monthly_sales: list[SalesPoint]
