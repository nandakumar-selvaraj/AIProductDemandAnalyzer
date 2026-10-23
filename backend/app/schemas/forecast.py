from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    horizon_days: int = Field(default=30, ge=1, le=30)
    start_date: date | None = Field(
        default=None, description="Cutoff date; defaults to latest sales date"
    )


class ForecastRunResponse(BaseModel):
    run_id: int
    status: str
    forecast_cutoff: date
    horizon_days: int
    series_processed: int
    series_excluded: int
    predictions_created: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
