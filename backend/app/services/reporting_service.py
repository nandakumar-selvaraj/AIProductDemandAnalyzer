"""Bounded read queries for catalogs, analytics and dashboard summaries."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ForecastRun, Product, ProductForecast, SalesHistory, Store
from app.services.recommendation_service import recommendation_for_series


def list_catalog(session: Session, kind: str, page: int, page_size: int, search: str | None):
    model = Product if kind == "products" else Store
    code = model.item_code if kind == "products" else model.store_code
    name = model.name
    query = select(model)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(code.ilike(pattern) | name.ilike(pattern))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = session.scalars(
        query.order_by(code, model.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return total, items


def product_analytics(
    session: Session,
    product_id: int,
    store_id: int | None,
    start_date: date | None,
    end_date: date | None,
):
    if session.get(Product, product_id) is None:
        return None
    latest_for_product = session.scalar(
        select(func.max(SalesHistory.sale_date)).where(SalesHistory.product_id == product_id)
    )
    if latest_for_product is None:
        return ((None, None, 0, 0), [], [])
    effective_end = end_date or latest_for_product
    effective_start = start_date or effective_end - timedelta(days=364)
    if start_date is not None and end_date is None:
        effective_end = min(latest_for_product, start_date + timedelta(days=364))
    if effective_end < effective_start:
        raise ValueError("Analytics date range has no available sales dates")
    if effective_end - effective_start > timedelta(days=364):
        raise ValueError("Product analytics date range cannot exceed 365 calendar days")
    filters = [SalesHistory.product_id == product_id]
    if store_id is not None:
        filters.append(SalesHistory.store_id == store_id)
    filters.extend(
        [SalesHistory.sale_date >= effective_start, SalesHistory.sale_date <= effective_end]
    )
    overall = session.execute(
        select(
            func.min(SalesHistory.sale_date),
            func.max(SalesHistory.sale_date),
            func.coalesce(func.sum(SalesHistory.units_sold), 0),
            func.count(func.distinct(SalesHistory.sale_date)),
        ).where(*filters)
    ).one()
    daily = session.execute(
        select(SalesHistory.sale_date, func.sum(SalesHistory.units_sold))
        .where(*filters)
        .group_by(SalesHistory.sale_date)
        .order_by(SalesHistory.sale_date)
    ).all()
    month = func.date_trunc("month", SalesHistory.sale_date).cast(SalesHistory.sale_date.type)
    monthly = session.execute(
        select(month, func.sum(SalesHistory.units_sold))
        .where(*filters)
        .group_by(month)
        .order_by(month)
    ).all()
    return overall, daily, monthly


def dashboard_summary(session: Session):
    products = session.scalar(select(func.count()).select_from(Product)) or 0
    stores = session.scalar(select(func.count()).select_from(Store)) or 0
    total, start, end = session.execute(
        select(
            func.coalesce(func.sum(SalesHistory.units_sold), 0),
            func.min(SalesHistory.sale_date),
            func.max(SalesHistory.sale_date),
        )
    ).one()
    month = func.date_trunc("month", SalesHistory.sale_date).cast(SalesHistory.sale_date.type)
    monthly = session.execute(
        select(month, func.sum(SalesHistory.units_sold)).group_by(month).order_by(month)
    ).all()
    run = session.scalar(
        select(ForecastRun)
        .where(ForecastRun.status == "completed")
        .order_by(ForecastRun.completed_at.desc().nullslast(), ForecastRun.id.desc())
        .limit(1)
    )
    latest = None
    if run:
        demand = session.scalar(
            select(func.coalesce(func.sum(ProductForecast.predicted_units), 0)).where(
                ProductForecast.forecast_run_id == run.id,
                ProductForecast.forecast_date > run.training_cutoff,
                ProductForecast.forecast_date
                <= run.training_cutoff + timedelta(days=run.horizon_days),
            )
        ) or Decimal(0)
        history_start = run.training_cutoff - timedelta(days=29)
        predictions = (
            select(
                ProductForecast.store_id.label("store_id"),
                ProductForecast.product_id.label("product_id"),
                func.avg(ProductForecast.predicted_units).label("forecast_average"),
                func.count(func.distinct(ProductForecast.forecast_date)).label("forecast_days"),
            )
            .where(
                ProductForecast.forecast_run_id == run.id,
                ProductForecast.forecast_date > run.training_cutoff,
                ProductForecast.forecast_date
                <= run.training_cutoff + timedelta(days=run.horizon_days),
            )
            .group_by(ProductForecast.store_id, ProductForecast.product_id)
            .subquery()
        )
        history = (
            select(
                SalesHistory.store_id.label("store_id"),
                SalesHistory.product_id.label("product_id"),
                func.sum(SalesHistory.units_sold).label("history_total"),
                func.count(func.distinct(SalesHistory.sale_date)).label("coverage"),
            )
            .where(SalesHistory.sale_date.between(history_start, run.training_cutoff))
            .group_by(SalesHistory.store_id, SalesHistory.product_id)
            .subquery()
        )
        recommendation_rows = session.execute(
            select(
                predictions.c.forecast_average,
                predictions.c.forecast_days,
                func.coalesce(history.c.history_total, 0).label("history_total"),
                func.coalesce(history.c.coverage, 0).label("coverage"),
            ).outerjoin(
                history,
                (history.c.store_id == predictions.c.store_id)
                & (history.c.product_id == predictions.c.product_id),
            )
        ).all()
        from app.core.config import get_settings

        settings = get_settings()
        counts = {key: 0 for key in ("increase", "maintain", "reduce", "insufficient_data")}
        for row in recommendation_rows:
            average = Decimal(str(row.forecast_average))
            category = recommendation_for_series(
                average,
                row.forecast_days,
                row.history_total,
                row.coverage,
                run.horizon_days,
                settings.recommendation_increase_threshold_percent,
                settings.recommendation_reduce_threshold_percent,
            )[0]
            counts[category] += 1
        latest = {
            "forecast_run_id": run.id,
            "training_cutoff": run.training_cutoff,
            "horizon_days": run.horizon_days,
            "forecast_demand_total": Decimal(demand),
            "recommendation_counts": {
                label: counts.get(label, 0)
                for label in ("increase", "maintain", "reduce", "insufficient_data")
            },
        }
    return products, stores, start, end, total, monthly, latest
