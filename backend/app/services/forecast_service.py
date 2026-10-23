"""Trailing-average baseline forecast implementation."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ForecastRun, ForecastRunLog, ProductForecast, SalesHistory

WINDOW_DAYS = 30


def trailing_average(values: list[int | None]) -> Decimal | None:
    """Return a mean only when all trailing calendar days are observed."""
    if len(values) != WINDOW_DAYS or any(value is None for value in values):
        return None
    return Decimal(sum(values)) / Decimal(WINDOW_DAYS)


def get_forecast_dates(cutoff: date, horizon_days: int) -> list[date]:
    return [cutoff + timedelta(days=offset) for offset in range(1, horizon_days + 1)]


def get_forecast_predictions(
    session: Session, run_id: int, page: int, page_size: int
) -> tuple[int, list[ProductForecast]] | None:
    """Return page of persisted predictions, or None when the run is missing."""
    run_exists = session.scalar(select(ForecastRun.id).where(ForecastRun.id == run_id))
    if run_exists is None:
        return None
    filters = ProductForecast.forecast_run_id == run_id
    total = session.scalar(select(func.count()).select_from(ProductForecast).where(filters)) or 0
    items = session.scalars(
        select(ProductForecast)
        .where(filters)
        .order_by(
            ProductForecast.forecast_date,
            ProductForecast.store_id,
            ProductForecast.product_id,
            ProductForecast.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return total, items


def create_forecast(
    session: Session, horizon_days: int, start_date: date | None = None
) -> ForecastRun:
    """Create run, predictions and success log in one transaction."""
    try:
        with session.begin():
            latest = session.scalar(select(func.max(SalesHistory.sale_date)))
            cutoff = start_date or latest
            if cutoff is None:
                raise ValueError("Sales history is empty; a forecast cannot be created")
            if latest is not None and cutoff > latest:
                raise ValueError("Forecast cutoff cannot be later than the latest sales date")

            run = ForecastRun(
                model_name="trailing_30_day_average",
                model_version="1",
                training_cutoff=cutoff,
                horizon_days=horizon_days,
                status="running",
                started_at=datetime.now(UTC),
            )
            session.add(run)
            session.flush()

            first_day = cutoff - timedelta(days=WINDOW_DAYS - 1)
            series = session.execute(
                select(SalesHistory.store_id, SalesHistory.product_id)
                .where(SalesHistory.sale_date <= cutoff)
                .distinct()
            ).all()
            history = session.execute(
                select(
                    SalesHistory.store_id,
                    SalesHistory.product_id,
                    SalesHistory.sale_date,
                    SalesHistory.units_sold,
                ).where(SalesHistory.sale_date.between(first_day, cutoff))
            ).all()
            by_series: dict[tuple[int, int], dict[date, int]] = {}
            for store_id, product_id, sale_date, units_sold in history:
                by_series.setdefault((store_id, product_id), {})[sale_date] = units_sold

            expected = [first_day + timedelta(days=i) for i in range(WINDOW_DAYS)]
            predictions = []
            processed = 0
            for store_id, product_id in series:
                observed = by_series.get((store_id, product_id), {})
                mean = trailing_average([observed.get(day) for day in expected])
                if mean is None:
                    continue
                processed += 1
                predictions.extend(
                    ProductForecast(
                        forecast_run_id=run.id,
                        store_id=store_id,
                        product_id=product_id,
                        forecast_date=day,
                        predicted_units=max(mean, Decimal(0)),
                    )
                    for day in get_forecast_dates(cutoff, horizon_days)
                )
            session.add_all(predictions)
            excluded = len(series) - processed
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            run.metrics_json = {
                "series_processed": processed,
                "series_excluded": excluded,
                "predictions_created": len(predictions),
                "missing_date_policy": "exclude series unless all 30 calendar days are observed",
            }
            session.add(
                ForecastRunLog(
                    forecast_run_id=run.id,
                    level="INFO",
                    message="Forecast run completed",
                    details_json=run.metrics_json,
                )
            )
        session.refresh(run)
        return run
    except Exception:
        session.rollback()
        raise
