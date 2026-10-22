import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import IngestionValidationError
from app.db.session import get_db
from app.schemas.ingestion import ErrorResponse, IngestionSummary
from app.services.ingestion_service import ingest_sales

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingestion", tags=["Data Ingestion"])


@router.post(
    "/sales",
    response_model=IngestionSummary,
    summary="Ingest Kaggle sales CSV",
    description=(
        "Uploads a UTF-8 CSV with `date`, `store`, `item`, and `sales` columns. "
        "Exact duplicate keys use the last row; existing daily totals are updated. "
        "The complete import is committed in one transaction."
    ),
    responses={
        200: {"description": "CSV validated and sales rows ingested"},
        413: {"model": ErrorResponse, "description": "Upload exceeds the configured size limit"},
        415: {
            "model": ErrorResponse,
            "description": "Uploaded file is not a supported CSV media type",
        },
        422: {"model": ErrorResponse, "description": "CSV contents or request are invalid"},
        503: {
            "model": ErrorResponse,
            "description": "Database is unavailable or rejected the transaction",
        },
        500: {"model": ErrorResponse, "description": "Unexpected ingestion failure"},
    },
)
async def ingest_sales_upload(
    file: UploadFile = File(
        ...,
        description=(
            "CSV file with date, store, item, and sales columns (maximum 25 MiB by default)."
        ),
    ),
    session: Session = Depends(get_db),
) -> IngestionSummary:
    if file.content_type not in {
        "text/csv",
        "application/vnd.ms-excel",
        "application/octet-stream",
    }:
        raise HTTPException(
            status_code=415,
            detail={"code": "unsupported_media_type", "message": "Upload a CSV file"},
        )
    content = await file.read(get_settings().max_upload_bytes + 1)
    await file.close()
    if len(content) > get_settings().max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail={"code": "file_too_large", "message": "CSV exceeds the configured upload limit"},
        )
    try:
        return ingest_sales(content, session)
    except IngestionValidationError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_csv", "message": str(exc)}
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Sales upload database failure")
        raise HTTPException(
            status_code=503,
            detail={"code": "database_error", "message": "Sales could not be stored"},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected sales upload failure")
        raise HTTPException(
            status_code=500, detail={"code": "internal_error", "message": "Sales ingestion failed"}
        ) from exc
