import logging
from datetime import date
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analytics import ProductAnalyticsResponse, SalesPoint
from app.schemas.catalog import CatalogPage, ProductListItem
from app.schemas.ingestion import ErrorResponse
from app.services.reporting_service import list_catalog, product_analytics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=CatalogPage, summary="List products")
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: str | None = Query(None, max_length=100),
    session: Session = Depends(get_db),
) -> CatalogPage:
    try:
        total, rows = list_catalog(session, "products", page, page_size, search)
        return CatalogPage(
            page=page,
            page_size=page_size,
            total_records=total,
            total_pages=ceil(total / page_size) if total else 0,
            items=[ProductListItem(id=p.id, item_code=p.item_code, name=p.name) for p in rows],
        )
    except SQLAlchemyError as exc:
        logger.exception("Product catalog query failed")
        raise HTTPException(
            503, detail={"code": "database_error", "message": "Products unavailable"}
        ) from exc


@router.get(
    "/{product_id}/analytics",
    response_model=ProductAnalyticsResponse,
    responses={404: {"model": ErrorResponse}, 422: {"description": "Invalid date range"}},
    summary="Get bounded product sales analytics",
)
def get_product_analytics(
    product_id: int = Path(..., gt=0),
    store_id: int | None = Query(None, gt=0),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    session: Session = Depends(get_db),
) -> ProductAnalyticsResponse:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            422,
            detail={
                "code": "invalid_date_range",
                "message": "start_date must not be after end_date",
            },
        )
    try:
        result = product_analytics(session, product_id, store_id, start_date, end_date)
    except ValueError as exc:
        raise HTTPException(
            422, detail={"code": "invalid_date_range", "message": str(exc)}
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Product analytics query failed")
        raise HTTPException(
            503, detail={"code": "database_error", "message": "Product analytics unavailable"}
        ) from exc
    if result is None:
        raise HTTPException(
            404, detail={"code": "product_not_found", "message": "Product was not found"}
        )
    overall, daily, monthly = result
    return ProductAnalyticsResponse(
        product_id=product_id,
        store_id=store_id,
        start_date=overall[0],
        end_date=overall[1],
        total_units_sold=overall[2],
        observed_dates=overall[3],
        daily_sales=[SalesPoint(period=row[0], units_sold=row[1]) for row in daily],
        monthly_sales=[SalesPoint(period=row[0], units_sold=row[1]) for row in monthly],
    )
