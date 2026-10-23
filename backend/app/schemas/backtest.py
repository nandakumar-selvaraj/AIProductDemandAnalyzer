from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cutoff_date: date
    horizon_days: int = Field(default=30, ge=1, le=30)


class BacktestMetrics(BaseModel):
    evaluated_predictions: int
    unmatched_predictions: int
    evaluated_series: int
    total_series: int
    coverage_percent: Decimal
    total_actual_units: int
    total_predicted_units: Decimal
    mae: Decimal | None
    wape_percent: Decimal | None
    evaluation_status: Literal["complete", "partial", "unavailable"]


class BacktestResponse(BaseModel):
    cutoff_date: date
    horizon_days: int
    holdout_start: date
    holdout_end: date
    missing_dates: list[date]
    models: dict[str, BacktestMetrics]
    assumptions: list[str]
