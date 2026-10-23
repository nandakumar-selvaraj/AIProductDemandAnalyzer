import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dashboard import DashboardForecast, DashboardSummary
from app.services.reporting_service import dashboard_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary, summary="Get dashboard summary")
def get_dashboard_summary(session: Session = Depends(get_db)) -> DashboardSummary:
    try:
        products, stores, start, end, total, monthly, latest = dashboard_summary(session)
    except SQLAlchemyError as exc:
        logger.exception("Dashboard summary query failed")
        raise HTTPException(
            503, detail={"code": "database_error", "message": "Dashboard summary unavailable"}
        ) from exc
    return DashboardSummary(
        product_count=products,
        store_count=stores,
        historical_start_date=start,
        historical_end_date=end,
        total_units_sold=total,
        monthly_sales=[(period, units) for period, units in monthly],
        latest_forecast=DashboardForecast(**latest) if latest else None,
    )
