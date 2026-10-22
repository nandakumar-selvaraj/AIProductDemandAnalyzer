"""Import all models so Alembic can discover metadata."""

from app.models.forecast_run import ForecastRun
from app.models.forecast_run_log import ForecastRunLog
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.product_forecast import ProductForecast
from app.models.sales_history import SalesHistory
from app.models.stock_recommendation import StockRecommendation
from app.models.store import Store

__all__ = [
    "ForecastRun",
    "ForecastRunLog",
    "Inventory",
    "Product",
    "ProductForecast",
    "SalesHistory",
    "StockRecommendation",
    "Store",
]
