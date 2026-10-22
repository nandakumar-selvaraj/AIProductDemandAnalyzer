from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ingestion import ErrorResponse, HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check application health",
    description=(
        "Confirms that the API process is responding. This check does not connect to PostgreSQL."
    ),
    responses={200: {"description": "Application is responsive"}},
)
async def health() -> HealthResponse:
    return {"status": "ok"}


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Check service readiness",
    description="Checks whether the application can reach PostgreSQL.",
    responses={503: {"model": ErrorResponse, "description": "Database is unavailable"}},
)
def ready(session: Session = Depends(get_db)) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "Database is unavailable"},
        ) from exc
    return HealthResponse(status="ready")
