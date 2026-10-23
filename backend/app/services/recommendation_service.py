"""On-demand forecast trend recommendations based on observed sales and forecasts."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ForecastRun, ProductForecast, SalesHistory

HISTORY_DAYS = 30


def recommendation_for_series(
    forecast_average: Decimal | None,
    forecast_days: int,
    historical_total: int,
    historical_coverage_days: int,
    horizon_days: int,
    increase_threshold: Decimal,
    reduce_threshold: Decimal,
) -> tuple[str, Decimal | None, Decimal | None, Decimal | None, str]:
    """Apply complete-window rules and trend thresholds to one series."""
    history_average = (
        Decimal(historical_total) / Decimal(HISTORY_DAYS)
        if historical_coverage_days == HISTORY_DAYS
        else None
    )
    if history_average is None:
        return (
            "insufficient_data",
            None,
            forecast_average,
            None,
            "Historical sales do not cover all 30 calendar dates.",
        )
    if forecast_average is None or forecast_days != horizon_days:
        return (
            "insufficient_data",
            history_average,
            forecast_average,
            None,
            "Forecast predictions do not cover the full run horizon.",
        )
    if history_average == 0:
        if forecast_average == 0:
            return (
                "maintain",
                history_average,
                forecast_average,
                Decimal(0),
                "Both historical and forecast demand are zero.",
            )
        return (
            "insufficient_data",
            history_average,
            forecast_average,
            None,
            "Percentage change cannot be calculated from zero historical demand.",
        )
    change = (forecast_average - history_average) / history_average * Decimal(100)
    if change >= increase_threshold:
        return (
            "increase",
            history_average,
            forecast_average,
            change,
            "Forecast daily demand is at least the increase threshold above history.",
        )
    if change <= reduce_threshold:
        return (
            "reduce",
            history_average,
            forecast_average,
            change,
            "Forecast daily demand is at least the reduction threshold below history.",
        )
    return (
        "maintain",
        history_average,
        forecast_average,
        change,
        "Forecast daily demand is within the configured thresholds.",
    )


def get_recommendations(
    session: Session,
    run_id: int,
    page: int,
    page_size: int,
    increase_threshold: Decimal,
    reduce_threshold: Decimal,
) -> tuple[int, list[dict[str, object]]] | None:
    """Aggregate per-series data in SQL, then paginate and classify series."""
    run = session.get(ForecastRun, run_id)
    if run is None:
        return None
    if run.status != "completed":
        raise ValueError("Recommendations require a completed forecast run")

    window_start = run.training_cutoff - timedelta(days=HISTORY_DAYS - 1)
    forecast_stats = (
        select(
            ProductForecast.store_id.label("store_id"),
            ProductForecast.product_id.label("product_id"),
            func.avg(ProductForecast.predicted_units).label("forecast_average"),
            func.count(func.distinct(ProductForecast.forecast_date)).label("forecast_days"),
        )
        .where(
            ProductForecast.forecast_run_id == run_id,
            ProductForecast.forecast_date > run.training_cutoff,
            ProductForecast.forecast_date <= run.training_cutoff + timedelta(days=run.horizon_days),
        )
        .group_by(ProductForecast.store_id, ProductForecast.product_id)
        .subquery()
    )
    history_stats = (
        select(
            SalesHistory.store_id.label("store_id"),
            SalesHistory.product_id.label("product_id"),
            func.sum(SalesHistory.units_sold).label("historical_total"),
            func.count(func.distinct(SalesHistory.sale_date)).label("coverage_days"),
        )
        .where(SalesHistory.sale_date.between(window_start, run.training_cutoff))
        .group_by(SalesHistory.store_id, SalesHistory.product_id)
        .subquery()
    )
    series_count = session.scalar(select(func.count()).select_from(forecast_stats)) or 0
    rows = session.execute(
        select(
            forecast_stats.c.store_id,
            forecast_stats.c.product_id,
            forecast_stats.c.forecast_average,
            forecast_stats.c.forecast_days,
            func.coalesce(history_stats.c.historical_total, 0).label("historical_total"),
            func.coalesce(history_stats.c.coverage_days, 0).label("coverage_days"),
        )
        .outerjoin(
            history_stats,
            (history_stats.c.store_id == forecast_stats.c.store_id)
            & (history_stats.c.product_id == forecast_stats.c.product_id),
        )
        .order_by(forecast_stats.c.store_id, forecast_stats.c.product_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    results: list[dict[str, object]] = []
    for row in rows:
        average = Decimal(str(row.forecast_average)) if row.forecast_average is not None else None
        label, history_avg, forecast_avg, change, reason = recommendation_for_series(
            average,
            row.forecast_days,
            row.historical_total,
            row.coverage_days,
            run.horizon_days,
            increase_threshold,
            reduce_threshold,
        )
        results.append(
            {
                "store_id": row.store_id,
                "product_id": row.product_id,
                "recommendation": label,
                "reason": reason,
                "historical_daily_average": history_avg,
                "forecast_daily_average": forecast_avg,
                "change_percent": change,
                "forecast_horizon_days": run.horizon_days,
                "historical_coverage_days": row.coverage_days,
                "historical_window_start": window_start,
                "historical_window_end": run.training_cutoff,
            }
        )
    return series_count, results
