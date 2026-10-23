import logging
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.ingestion import ErrorResponse
from app.schemas.recommendations import RecommendationsResponse
from app.services.recommendation_service import get_recommendations

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Recommendations"])


@router.get(
    "/recommendations",
    response_model=RecommendationsResponse,
    summary="Get forecast-based demand trend recommendations",
    description=(
        "Compares each series' forecast daily average with its 30-day historical daily average. "
        "Only complete historical windows and complete forecast horizons receive trend labels. "
        "This does not estimate on-hand inventory or order quantities."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Forecast run does not exist"},
        409: {"model": ErrorResponse, "description": "Forecast run is not completed"},
        422: {"description": "Invalid query parameters"},
        503: {"model": ErrorResponse, "description": "Database is unavailable"},
    },
)
def list_recommendations(
    forecast_run_id: int = Query(..., gt=0, description="Completed forecast run ID"),
    page: int = Query(1, ge=1, description="Page number, starting at 1"),
    page_size: int = Query(50, ge=1, le=500, description="Results per page (maximum 500)"),
    session: Session = Depends(get_db),
) -> RecommendationsResponse:
    settings = get_settings()
    try:
        result = get_recommendations(
            session,
            forecast_run_id,
            page,
            page_size,
            settings.recommendation_increase_threshold_percent,
            settings.recommendation_reduce_threshold_percent,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "forecast_not_completed", "message": str(exc)},
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Recommendation query failed")
        raise HTTPException(
            status_code=503,
            detail={"code": "database_error", "message": "Recommendations are unavailable"},
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "forecast_not_found", "message": "Forecast run was not found"},
        )
    total, items = result
    return RecommendationsResponse(
        forecast_run_id=forecast_run_id,
        page=page,
        page_size=page_size,
        total_records=total,
        total_pages=ceil(total / page_size) if total else 0,
        increase_threshold_percent=settings.recommendation_increase_threshold_percent,
        reduce_threshold_percent=settings.recommendation_reduce_threshold_percent,
        items=items,
    )
