"""Trailing-average baseline forecast implementation."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
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


def evaluate_forecast(
    session: Session, run_id: int
) -> tuple[ForecastRun, dict[str, object]] | None:
    """Aggregate prediction accuracy against actual sales on forecast dates only."""
    run = session.get(ForecastRun, run_id)
    if run is None:
        return None
    if run.status != "completed":
        raise ValueError("Only completed runs can be evaluated")

    actual_join = (
        (ProductForecast.store_id == SalesHistory.store_id)
        & (ProductForecast.product_id == SalesHistory.product_id)
        & (ProductForecast.forecast_date == SalesHistory.sale_date)
        & (ProductForecast.forecast_date > run.training_cutoff)
        & (ProductForecast.forecast_date <= run.training_cutoff + timedelta(days=run.horizon_days))
    )
    matched = SalesHistory.id.is_not(None)
    aggregate = session.execute(
        select(
            func.count(ProductForecast.id).label("total_predictions"),
            func.count(SalesHistory.id).label("evaluated_predictions"),
            func.coalesce(func.sum(func.coalesce(SalesHistory.units_sold, 0)), 0).label(
                "total_actual_units"
            ),
            func.coalesce(
                func.sum(case((matched, ProductForecast.predicted_units), else_=0)), 0
            ).label("total_predicted_units"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            matched,
                            func.abs(ProductForecast.predicted_units - SalesHistory.units_sold),
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("absolute_error_sum"),
        )
        .select_from(ProductForecast)
        .outerjoin(SalesHistory, actual_join)
        .where(ProductForecast.forecast_run_id == run_id)
    ).one()
    total_predictions = aggregate.total_predictions
    evaluated = aggregate.evaluated_predictions
    unmatched = total_predictions - evaluated
    actual_total = int(aggregate.total_actual_units)
    predicted_total = Decimal(aggregate.total_predicted_units)
    error_sum = Decimal(aggregate.absolute_error_sum)
    mae = error_sum / evaluated if evaluated else None
    wape = (error_sum * Decimal(100) / actual_total) if evaluated and actual_total else None
    coverage = (
        Decimal(evaluated) * Decimal(100) / Decimal(total_predictions)
        if total_predictions
        else Decimal(0)
    )
    status = "unavailable" if not evaluated else "complete" if unmatched == 0 else "partial"
    return run, {
        "evaluated_predictions": evaluated,
        "unmatched_predictions": unmatched,
        "total_predictions": total_predictions,
        "coverage_percent": coverage,
        "total_actual_units": actual_total,
        "total_predicted_units": predicted_total,
        "mae": mae,
        "wape_percent": wape,
        "evaluation_status": status,
    }


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
