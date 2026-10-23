from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DashboardForecast(BaseModel):
    forecast_run_id: int
    training_cutoff: date
    horizon_days: int
    forecast_demand_total: Decimal
    recommendation_counts: dict[str, int]


class DashboardSummary(BaseModel):
    product_count: int
    store_count: int
    historical_start_date: date | None
    historical_end_date: date | None
    total_units_sold: int
    monthly_sales: list[tuple[date, int]]
    latest_forecast: DashboardForecast | None
