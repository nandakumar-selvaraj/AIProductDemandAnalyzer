from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecommendationItem(BaseModel):
    store_id: int
    product_id: int
    recommendation: Literal["increase", "maintain", "reduce", "insufficient_data"]
    reason: str
    historical_daily_average: Decimal | None = Field(
        description="Mean actual units per calendar day across the 30-day history window"
    )
    forecast_daily_average: Decimal | None = Field(
        description="Mean predicted units per forecast day across this run's full horizon"
    )
    change_percent: Decimal | None = Field(
        description="Relative change from historical to forecast mean, as a percentage"
    )
    forecast_horizon_days: int
    historical_coverage_days: int = Field(ge=0, le=30)
    historical_window_start: date
    historical_window_end: date


class RecommendationsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast_run_id: int
    page: int
    page_size: int
    total_records: int
    total_pages: int
    increase_threshold_percent: Decimal
    reduce_threshold_percent: Decimal
    items: list[RecommendationItem]
