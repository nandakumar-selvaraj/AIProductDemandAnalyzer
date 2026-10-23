import logging
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.catalog import StoreListItem, StorePage
from app.services.reporting_service import list_catalog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stores", tags=["Stores"])


@router.get("", response_model=StorePage, summary="List stores")
def list_stores(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: str | None = Query(None, max_length=100),
    session: Session = Depends(get_db),
) -> StorePage:
    try:
        total, rows = list_catalog(session, "stores", page, page_size, search)
        return StorePage(
            page=page,
            page_size=page_size,
            total_records=total,
            total_pages=ceil(total / page_size) if total else 0,
            items=[StoreListItem(id=s.id, store_code=s.store_code, name=s.name) for s in rows],
        )
    except SQLAlchemyError as exc:
        logger.exception("Store catalog query failed")
        raise HTTPException(
            503, detail={"code": "database_error", "message": "Stores unavailable"}
        ) from exc
