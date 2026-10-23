"""FastAPI application entry point."""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.v1.router import api_router
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)
configure_logging()
app = FastAPI(
    title="AI Product Demand Analyzer API",
    description=(
        "Backend API for importing and summarizing historical product sales and checking "
        "service health. Sales ingestion accepts the Kaggle competition CSV schema. Forecast "
        "runs use a trailing-average baseline; persisted predictions can be retrieved with "
        "pagination and evaluated against matching actual sales. Demand-trend recommendations "
        "are available from persisted forecasts and sales history. Catalog, product analytics, "
        "dashboard and historical backtest endpoints support the reporting workflow. "
        "Authentication is not implemented in this version."
    ),
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Health",
            "description": "Process health and PostgreSQL readiness checks.",
        },
        {
            "name": "Data Ingestion",
            "description": "Validated CSV upload and repeatable sales ingestion.",
        },
        {
            "name": "Sales",
            "description": "Aggregated sales reporting for ingested history.",
        },
        {
            "name": "Forecasts",
            "description": (
                "Create trailing-average forecast runs, retrieve paginated persisted predictions, "
                "and evaluate completed runs against matching actual sales."
            ),
        },
        {
            "name": "Recommendations",
            "description": (
                "Forecast-based demand trend recommendations with historical coverage; exact "
                "inventory quantities are not inferred."
            ),
        },
        {
            "name": "Products",
            "description": "Paginated product catalog and bounded sales analytics.",
        },
        {"name": "Stores", "description": "Paginated store catalog."},
        {
            "name": "Dashboard",
            "description": "Database-derived summary for the latest completed forecast.",
        },
    ],
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Open the interactive API documentation at the service root."""
    return RedirectResponse(url="/docs")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "request_validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        error = detail
    else:
        error = {"code": "http_error", "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": error}, headers=exc.headers)


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "An unexpected error occurred"}},
    )
