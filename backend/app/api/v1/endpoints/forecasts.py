import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.forecast import ForecastRequest, ForecastRunResponse
from app.schemas.ingestion import ErrorResponse
from app.services.forecast_service import create_forecast

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
