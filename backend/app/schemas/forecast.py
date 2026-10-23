from datetime import date, datetime
from decimal import Decimal

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


class ForecastPredictionItem(BaseModel):
    """Persisted daily prediction fields from ProductForecast."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    forecast_run_id: int
    store_id: int
    product_id: int
    forecast_date: date
    predicted_units: Decimal


class ForecastPredictionsResponse(BaseModel):
    run_id: int
    page: int
    page_size: int
    total_records: int
    total_pages: int
    items: list[ForecastPredictionItem]


class ForecastEvaluationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"forecast_run_id": 1}]},
    )

    forecast_run_id: int = Field(gt=0, description="Completed forecast run to evaluate")


class ForecastEvaluationResponse(BaseModel):
    forecast_run_id: int
    forecast_cutoff: date
    horizon_days: int
    total_predictions: int = Field(description="All stored predictions belonging to this run")
    evaluated_predictions: int = Field(
        description="Predictions with actual sales for the same store, product, and forecast date"
    )
    unmatched_predictions: int = Field(
        description="Stored predictions without matching actual sales"
    )
    coverage_percent: Decimal = Field(
        description="Evaluated predictions divided by total predictions, as a percentage"
    )
    total_actual_units: int = Field(description="Actual units among evaluated predictions")
    total_predicted_units: Decimal = Field(
        description="Predicted units among evaluated predictions"
    )
    mae: Decimal | None = Field(
        description="Mean absolute error in units among matches; null if no matches"
    )
    wape_percent: Decimal | None = Field(
        description="Weighted absolute percentage error; null if no matches or actual total is zero"
    )
    evaluation_status: str = Field(
        description=(
            "complete when all stored predictions matched, partial when some matched, "
            "unavailable when none matched or there were no predictions"
        ),
        examples=["complete", "partial", "unavailable"],
    )


class ForecastRunItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_name: str
    model_version: str | None
    training_cutoff: date
    horizon_days: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    metrics_json: dict[str, object] | None


class ForecastRunPage(BaseModel):
    page: int
    page_size: int
    total_records: int
    total_pages: int
    items: list[ForecastRunItem]
