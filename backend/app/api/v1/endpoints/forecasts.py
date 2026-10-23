import logging
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.forecast import (
    ForecastPredictionsResponse,
    ForecastRequest,
    ForecastRunResponse,
)
from app.schemas.ingestion import ErrorResponse
from app.services.forecast_service import create_forecast, get_forecast_predictions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/forecasts", tags=["Forecasts"])


@router.post(
    "",
    response_model=ForecastRunResponse,
    summary="Create a demand forecast",
    description=(
        "Averages each store/product series over the 30 calendar days through the cutoff. "
        "Series with missing dates are excluded; missing rows are not assumed to be zero."
    ),
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def post_forecast(
    request: ForecastRequest, session: Session = Depends(get_db)
) -> ForecastRunResponse:
    try:
        run = create_forecast(session, request.horizon_days, request.start_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_forecast", "message": str(exc)}
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Forecast persistence failed")
        raise HTTPException(
            status_code=503,
            detail={"code": "database_error", "message": "Forecast could not be created"},
        ) from exc
    metrics = run.metrics_json or {}
    return ForecastRunResponse(
        run_id=run.id,
        status=run.status,
        forecast_cutoff=run.training_cutoff,
        horizon_days=run.horizon_days,
        series_processed=metrics.get("series_processed", 0),
        series_excluded=metrics.get("series_excluded", 0),
        predictions_created=metrics.get("predictions_created", 0),
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get(
    "/{run_id}/predictions",
    response_model=ForecastPredictionsResponse,
    summary="List persisted forecast predictions",
    description=(
        "Returns stored predictions in ascending forecast date, store ID, product ID, "
        "and prediction ID order. A valid run with no predictions returns an empty items list."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Forecast run does not exist"},
        422: {"description": "Invalid run ID or pagination parameters"},
        503: {"model": ErrorResponse, "description": "Database is unavailable"},
    },
)
def list_forecast_predictions(
    run_id: int = Path(..., gt=0, description="Forecast run identifier"),
    page: int = Query(default=1, ge=1, description="Page number, starting at 1"),
    page_size: int = Query(default=50, ge=1, le=500, description="Records per page (maximum 500)"),
    session: Session = Depends(get_db),
) -> ForecastPredictionsResponse:
    try:
        result = get_forecast_predictions(session, run_id, page, page_size)
    except SQLAlchemyError as exc:
        logger.exception("Forecast predictions query failed")
        raise HTTPException(
            status_code=503,
            detail={"code": "database_error", "message": "Forecast predictions are unavailable"},
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "forecast_not_found", "message": "Forecast run was not found"},
        )
    total, predictions = result
    return ForecastPredictionsResponse(
        run_id=run_id,
        page=page,
        page_size=page_size,
        total_records=total,
        total_pages=ceil(total / page_size) if total else 0,
        items=predictions,
    )
