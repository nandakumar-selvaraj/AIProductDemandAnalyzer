from fastapi import APIRouter

from app.api.v1.endpoints import (
    dashboard,
    forecasts,
    health,
    ingestion,
    products,
    recommendations,
    sales,
    stores,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ingestion.router)
api_router.include_router(sales.router)
api_router.include_router(forecasts.router)
api_router.include_router(recommendations.router)
api_router.include_router(products.router)
api_router.include_router(stores.router)
api_router.include_router(dashboard.router)
