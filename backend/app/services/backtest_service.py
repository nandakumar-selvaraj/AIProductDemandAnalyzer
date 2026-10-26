"""Leakage-safe, non-persisted historical model comparison."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SalesHistory


def run_backtest(
    session: Session,
    cutoff: date,
    horizon: int,
    *,
    product_id: int | None = None,
    store_id: int | None = None,
) -> dict[str, object]:
    scope = []
    if product_id is not None:
        scope.append(SalesHistory.product_id == product_id)
    if store_id is not None:
        scope.append(SalesHistory.store_id == store_id)
    holdout_dates = [cutoff + timedelta(days=offset) for offset in range(1, horizon + 1)]
    history_start = cutoff - timedelta(days=29)
    train_rows = session.execute(
        select(
            SalesHistory.store_id,
            SalesHistory.product_id,
            SalesHistory.sale_date,
            SalesHistory.units_sold,
        ).where(SalesHistory.sale_date.between(history_start, cutoff), *scope)
    ).all()
    train: dict[tuple[int, int], dict[date, int]] = defaultdict(dict)
    for store, product, day, units in train_rows:
        train[(store, product)][day] = units
    if not train:
        raise ValueError("No training sales exist on or before the cutoff")

    # Predictions are constructed exclusively from train, before holdout is queried.
    predictions: dict[str, dict[tuple[int, int, date], Decimal]] = {
        "trailing_average": {},
        "seasonal_naive": {},
    }
    for key, values in train.items():
        thirty = [values.get(history_start + timedelta(days=i)) for i in range(30)]
        if all(value is not None for value in thirty):
            mean = Decimal(sum(thirty)) / Decimal(30)
            for day in holdout_dates:
                predictions["trailing_average"][(key[0], key[1], day)] = mean
        last_week = [values.get(cutoff - timedelta(days=i)) for i in range(6, -1, -1)]
        if all(value is not None for value in last_week):
            for day in holdout_dates:
                predictions["seasonal_naive"][(key[0], key[1], day)] = Decimal(
                    last_week[(day.weekday() - (cutoff - timedelta(days=6)).weekday()) % 7]
                )

    holdout_rows = session.execute(
        select(
            SalesHistory.store_id,
            SalesHistory.product_id,
            SalesHistory.sale_date,
            SalesHistory.units_sold,
        ).where(SalesHistory.sale_date.in_(holdout_dates), *scope)
    ).all()
    actuals = {(store, product, day): units for store, product, day, units in holdout_rows}
    missing_dates = sorted(set(holdout_dates) - {row[2] for row in holdout_rows})
    if missing_dates:
        raise ValueError("Actual sales do not cover every date in the requested holdout window")

    metrics: dict[str, dict[str, object]] = {}
    for model_name, model_predictions in predictions.items():
        absolute_error = Decimal(0)
        predicted_total = Decimal(0)
        actual_total = 0
        evaluated = 0
        evaluated_series: set[tuple[int, int]] = set()
        for key, predicted in model_predictions.items():
            actual = actuals.get(key)
            if actual is None:
                continue
            evaluated += 1
            evaluated_series.add((key[0], key[1]))
            actual_total += actual
            predicted_total += predicted
            absolute_error += abs(predicted - Decimal(actual))
        unmatched = len(model_predictions) - evaluated
        mae = absolute_error / evaluated if evaluated else None
        wape = absolute_error * 100 / actual_total if evaluated and actual_total else None
        coverage = (
            Decimal(evaluated) * 100 / len(model_predictions) if model_predictions else Decimal(0)
        )
        status = "unavailable" if not evaluated else "partial" if unmatched else "complete"
        metrics[model_name] = {
            "evaluated_predictions": evaluated,
            "unmatched_predictions": unmatched,
            "evaluated_series": len(evaluated_series),
            "total_series": len({(s, p) for s, p, _ in model_predictions}),
            "coverage_percent": coverage,
            "total_actual_units": actual_total,
            "total_predicted_units": predicted_total,
            "mae": mae,
            "wape_percent": wape,
            "evaluation_status": status,
        }
    return {
        "cutoff_date": cutoff,
        "horizon_days": horizon,
        "holdout_start": holdout_dates[0],
        "holdout_end": holdout_dates[-1],
        "missing_dates": [],
        "models": metrics,
        "assumptions": [
            "Only sales on or before cutoff were read to generate predictions.",
            "Trailing average requires all 30 training dates; missing rows are not zero-filled.",
            (
                "Seasonal naive repeats the last observed matching weekday and requires all "
                "prior seven training dates."
            ),
            (
                "Holdout actuals are read only after predictions are generated; unmatched "
                "series are excluded from errors and counted."
            ),
        ],
    }
