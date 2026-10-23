"""Sales reporting endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import SalesHistory
from app.schemas.ingestion import ErrorResponse
from app.schemas.sales import DailySalesSummary, SalesSummary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sales", tags=["Sales"])


@router.get(
    "/summary",
    response_model=SalesSummary,
    summary="Get sales summary",
    description=(
        "Returns the inclusive date range present in sales history, total units sold, "
        "distinct stores and products represented in sales, and totals grouped by day."
    ),
    responses={
        200: {"description": "Sales summary retrieved"},
        503: {"model": ErrorResponse, "description": "Database is unavailable"},
    },
)
def get_sales_summary(session: Session = Depends(get_db)) -> SalesSummary:
    try:
        overall = session.execute(
            select(
                func.min(SalesHistory.sale_date),
                func.max(SalesHistory.sale_date),
                func.coalesce(func.sum(SalesHistory.units_sold), 0),
                func.count(func.distinct(SalesHistory.store_id)),
                func.count(func.distinct(SalesHistory.product_id)),
            )
        ).one()
        daily_rows = session.execute(
            select(
                SalesHistory.sale_date,
                func.sum(SalesHistory.units_sold).label("total_sales"),
            )
            .group_by(SalesHistory.sale_date)
            .order_by(SalesHistory.sale_date)
        ).all()
    except SQLAlchemyError as exc:
        logger.exception("Sales summary database failure")
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "Sales summary is unavailable"},
        ) from exc

    start_date, end_date, total_sales, store_count, product_count = overall
    return SalesSummary(
        start_date=start_date,
        end_date=end_date,
        total_sales=total_sales,
        store_count=store_count,
        product_count=product_count,
        daily_sales=[
            DailySalesSummary(sale_date=sale_date, total_sales=daily_total)
            for sale_date, daily_total in daily_rows
        ],
    )
