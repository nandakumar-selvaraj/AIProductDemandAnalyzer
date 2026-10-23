from fastapi import APIRouter

from app.api.v1.endpoints import health, ingestion, sales

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ingestion.router)
api_router.include_router(sales.router)
