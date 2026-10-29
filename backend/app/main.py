"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import SecurityMiddleware

logger = logging.getLogger(__name__)
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.public_demo_enabled:
        from starlette.concurrency import run_in_threadpool

        from app.db.session import verify_demo_database

        await run_in_threadpool(verify_demo_database)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="AI Product Demand Analyzer API",
    description=(
        "Backend API for importing and summarizing historical product sales and checking "
        "service health. Sales ingestion accepts the Kaggle competition CSV schema. Forecast "
        "runs use a trailing-average baseline; persisted predictions can be retrieved with "
        "pagination and evaluated against matching actual sales. Demand-trend recommendations "
        "are available from persisted forecasts and sales history. Catalog, product analytics, "
        "dashboard and historical backtest endpoints support the reporting workflow. "
        "Production sensitive operations require operator authentication."
    ),
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    redoc_url="/redoc",
    swagger_ui_parameters={"persistAuthorization": False},
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
        {
            "name": "Assistant",
            "description": "Grounded business chat through a private AI provider.",
        },
    ],
)
app.include_router(api_router, prefix="/api/v1")
app.add_middleware(SecurityMiddleware)


def documented_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "ApiBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Owner CLI-issued API token only (1–15 minutes). Browser JWTs are rejected. "
                "RBAC and server-side revocation apply. Use a separate cookie-free Swagger "
                "session; never persist authorization."
            ),
        },
        "BrowserSession": {
            "type": "apiKey",
            "in": "cookie",
            "name": "__Host-demand_session",
            "description": (
                "HttpOnly browser session (demand_session in development). Browser mutations "
                "also require an allowed Origin and session-bound X-CSRF-Token. "
                "Not settable through Swagger."
            ),
        },
    }
    public = {"/api/v1/auth/login", "/api/v1/health", "/api/v1/ready", "/api/v1/demo/config"}
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if path not in public:
                operation["security"] = [{"BrowserSession": []}]
                if not path.startswith("/api/v1/auth/"):
                    operation["security"].append({"ApiBearer": []})
                operation.setdefault("responses", {}).update(
                    {
                        "401": {"description": "Missing, invalid, expired or revoked credential"},
                        "403": {"description": "Role denied or browser CSRF validation failed"},
                    }
                )
    app.openapi_schema = schema
    return schema


app.openapi = documented_openapi


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Open the interactive API documentation at the service root."""
    return RedirectResponse(url="/docs")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "request_validation_error",
                "message": "Request validation failed",
                "details": (
                    None
                    if get_settings().environment == "production"
                    or request.url.path.startswith("/api/v1/auth/")
                    else jsonable_encoder(exc.errors(), custom_encoder={ValueError: str})
                ),
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
