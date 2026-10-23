import logging
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.backtest import BacktestRequest, BacktestResponse
from app.schemas.forecast import (
    ForecastEvaluationRequest,
    ForecastEvaluationResponse,
    ForecastPredictionsResponse,
    ForecastRequest,
    ForecastRunItem,
    ForecastRunPage,
    ForecastRunResponse,
)
from app.schemas.ingestion import ErrorResponse
from app.services.backtest_service import run_backtest
from app.services.forecast_service import (
    create_forecast,
    evaluate_forecast,
    get_forecast_predictions,
    get_forecast_runs,
    get_latest_completed_forecast,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/forecasts", tags=["Forecasts"])


@router.get(
    "/latest", response_model=ForecastRunItem | None, summary="Get latest completed forecast"
)
def latest_forecast(session: Session = Depends(get_db)) -> ForecastRunItem | None:
    try:
        run = get_latest_completed_forecast(session)
        return ForecastRunItem.model_validate(run) if run else None
    except SQLAlchemyError as exc:
        logger.exception("Latest forecast query failed")
        raise HTTPException(
            503, detail={"code": "database_error", "message": "Forecast is unavailable"}
        ) from exc


@router.get("/runs", response_model=ForecastRunPage, summary="List forecast runs")
def list_forecast_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status: str | None = Query(None, pattern="^(pending|running|completed|failed)$"),
    session: Session = Depends(get_db),
) -> ForecastRunPage:
    try:
        total, runs = get_forecast_runs(session, page, page_size, status)
        return ForecastRunPage(
            page=page,
            page_size=page_size,
            total_records=total,
            total_pages=ceil(total / page_size) if total else 0,
            items=[ForecastRunItem.model_validate(run) for run in runs],
        )
    except SQLAlchemyError as exc:
        logger.exception("Forecast run list query failed")
        raise HTTPException(
            503, detail={"code": "database_error", "message": "Forecast runs unavailable"}
        ) from exc


@router.post(
    "/backtest",
    response_model=BacktestResponse,
    summary="Backtest forecast baselines",
    description=(
        "Compares trailing-30-day average and weekday seasonal-naive predictions at a historical "
        "cutoff. Models use training records only; holdout actuals are queried afterward. "
        "Missing actuals are unmatched, never zero-filled."
    ),
)
def forecast_backtest(
    request: BacktestRequest, session: Session = Depends(get_db)
) -> BacktestResponse:
    try:
        result = run_backtest(session, request.cutoff_date, request.horizon_days)
        return BacktestResponse(**result)
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "invalid_backtest", "message": str(exc)}) from exc
    except SQLAlchemyError as exc:
        logger.exception("Forecast backtest query failed")
        raise HTTPException(
            503, detail={"code": "database_error", "message": "Backtest unavailable"}
        ) from exc


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


@router.post(
    "/evaluate",
    response_model=ForecastEvaluationResponse,
    summary="Evaluate a completed forecast run",
    description=(
        "Compares persisted predictions with actual sales on matching store, product, and "
        "forecast dates only. Unmatched predictions are reported in coverage metadata. "
        "WAPE is null when no predictions match or actual units sum to zero."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Forecast run does not exist"},
        409: {"model": ErrorResponse, "description": "Forecast run is not completed"},
        422: {"description": "Invalid forecast run ID"},
        503: {"model": ErrorResponse, "description": "Database is unavailable"},
    },
)
def post_forecast_evaluation(
    request: ForecastEvaluationRequest, session: Session = Depends(get_db)
) -> ForecastEvaluationResponse:
    try:
        result = evaluate_forecast(session, request.forecast_run_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "forecast_not_completed", "message": str(exc)},
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Forecast evaluation query failed")
        raise HTTPException(
            status_code=503,
            detail={"code": "database_error", "message": "Forecast evaluation is unavailable"},
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "forecast_not_found", "message": "Forecast run was not found"},
        )
    run, metrics = result
    return ForecastEvaluationResponse(
        forecast_run_id=run.id,
        forecast_cutoff=run.training_cutoff,
        horizon_days=run.horizon_days,
        **metrics,
    )
