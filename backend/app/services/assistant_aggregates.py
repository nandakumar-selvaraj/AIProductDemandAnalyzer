"Complete scoped SQL aggregates and bounded use of the existing backtest service."

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import case, func, select

from app.models import ProductForecast, SalesHistory
from app.schemas.assistant import AssistantSource
from app.services.backtest_service import run_backtest


def historical_aggregate(db, context, question, limit, evidence):
    filters = []
    if context.store_id:
        filters.append(SalesHistory.store_id == context.store_id)
    if context.product_id:
        filters.append(SalesHistory.product_id == context.product_id)
    latest = db.scalar(select(func.max(SalesHistory.sale_date)).where(*filters))
    if latest is None:
        evidence.warnings.append("No historical observations exist in this scope.")
        return
    end = context.end_date or latest
    start = context.start_date or end - timedelta(days=364)
    if context.start_date and not context.end_date:
        end = min(latest, start + timedelta(days=364))
    if not 0 <= (end - start).days <= 364:
        raise ValueError("Invalid historical date range")
    filters.append(SalesHistory.sale_date.between(start, end))
    source = dict(type="historical", store_id=context.store_id, start_date=start, end_date=end)
    if "declin" in question.lower() or "decreas" in question.lower():
        if start == end:
            evidence.warnings.append(
                "Choose at least two calendar days for a historical comparison."
            )
            return
        midpoint = start + timedelta(days=((end - start).days + 1) // 2)
        early = SalesHistory.sale_date < midpoint
        late = SalesHistory.sale_date >= midpoint
        first_total = func.sum(case((early, SalesHistory.units_sold), else_=0))
        last_total = func.sum(case((late, SalesHistory.units_sold), else_=0))
        first_days = func.count(func.distinct(case((early, SalesHistory.sale_date))))
        last_days = func.count(func.distinct(case((late, SalesHistory.sale_date))))
        rows = db.execute(
            select(SalesHistory.product_id, first_total, first_days, last_total, last_days)
            .where(*filters)
            .group_by(SalesHistory.product_id)
            .having(
                first_days > 0,
                last_days > 0,
                first_total > 0,
                last_total * first_days < first_total * last_days,
            )
            .order_by(SalesHistory.product_id)
            .limit(limit)
        ).all()
        for product, first, first_count, last, last_count in rows:
            before, after = Decimal(first) / first_count, Decimal(last) / last_count
            change = (after - before) / before * 100
            evidence.add(
                f"Product #{product}: average units per observed sales date changed from {before} "
                f"in {start} to {midpoint - timedelta(days=1)} ({first_count} observed dates) "
                f"to {after} in {midpoint} to {end} ({last_count} observed dates), "
                f"a {change}% change. "
                "This is a historical split-window comparison, not a forecast.",
                AssistantSource(
                    id="", product_id=product, label="Historical decline comparison", **source
                ),
                {
                    "first_average": before,
                    "last_average": after,
                    "change_percent": change,
                    "first_observed_dates": first_count,
                    "last_observed_dates": last_count,
                },
            )
        evidence.warnings.append(
            "Declining observed-date averages are filtered across the complete "
            "date scope in SQL; shown in product-ID order, capped by the "
            "evidence limit. Missing dates are excluded, not zero-filled; "
            "changing observation/store coverage limits comparison."
        )
    elif "average" in question.lower():
        total, days = db.execute(
            select(
                func.sum(SalesHistory.units_sold), func.count(func.distinct(SalesHistory.sale_date))
            ).where(*filters)
        ).one()
        if not days:
            evidence.warnings.append("No observed sales dates match this historical range.")
            return
        average = Decimal(total) / days
        evidence.add(
            (
                f"Historical scope {start} to {end}: {total} recorded "
                f"units across {days} observed sales dates. Average "
                f"per observed sales date: {average} units, not "
                f"an average over missing calendar days."
            ),
            AssistantSource(
                id="",
                product_id=context.product_id,
                label="Historical observed-date average",
                **source,
            ),
            {"total_units": total, "observed_dates": days, "average_per_observed_date": average},
        )
    else:
        total = func.sum(SalesHistory.units_sold)
        rows = db.execute(
            select(
                SalesHistory.product_id, total, func.count(func.distinct(SalesHistory.sale_date))
            )
            .where(*filters)
            .group_by(SalesHistory.product_id)
            .order_by(total.desc(), SalesHistory.product_id)
            .limit(limit)
        ).all()
        for product, units, days in rows:
            average = Decimal(units) / days
            evidence.add(
                (
                    f"Product #{product}: {units} recorded historical "
                    f"units across {days} observed dates in {start} "
                    f"to {end}; {average} units per observed date. Ranked "
                    f"by complete scoped historical totals, not one "
                    f"page."
                ),
                AssistantSource(
                    id="", product_id=product, label="Historical product aggregate", **source
                ),
                {
                    "total_units": units,
                    "observed_dates": days,
                    "average_per_observed_date": average,
                },
            )
        evidence.warnings.append(
            f"Historical product ranking uses all matching records "
            f"in SQL, returns at most {limit} products, and "
            f"covers at most 365 inclusive days. Missing dates "
            f"are not zero."
        )


def forecast_stores(db, context, run, filters, evidence, limit, common):
    if not context.product_id:
        evidence.warnings.append("Select or name one product to compare forecasts across stores.")
        return
    rows = db.execute(
        select(ProductForecast.store_id, func.sum(ProductForecast.predicted_units), func.count())
        .where(*filters)
        .group_by(ProductForecast.store_id)
        .order_by(ProductForecast.store_id)
        .limit(limit)
    ).all()
    for store, units, count in rows:
        evidence.add(
            (
                f"Run #{run.id}, product #{context.product_id}, "
                f"store #{store}: {units} predicted units across "
                f"{count} persisted predictions in {common['start_date']} "
                f"to {common['end_date']}. This is an estimate, "
                f"not actual sales."
            ),
            AssistantSource(
                id="",
                type="forecast",
                product_id=context.product_id,
                store_id=store,
                label="Store prediction aggregate",
                **common,
            ),
            {"predicted_units": units, "predictions": count},
        )
    evidence.warnings.append(
        f"Store comparison uses complete scoped SQL aggregates, "
        f"shown in store-ID order, capped at {limit} stores."
    )


def backtest_evidence(db, context, evidence):
    cutoff = context.backtest_cutoff
    if cutoff is None:
        evidence.warnings.append(
            "Backtests are not persisted. Choose a historical backtest cutoff "
            "and a 1–30 day horizon; a method cannot be declared better "
            "without measured holdout results."
        )
        return
    horizon = context.backtest_horizon_days
    filters = [
        SalesHistory.sale_date.between(
            cutoff - timedelta(days=29), cutoff + timedelta(days=horizon)
        )
    ]
    if context.product_id:
        filters.append(SalesHistory.product_id == context.product_id)
    if context.store_id:
        filters.append(SalesHistory.store_id == context.store_id)
    count = db.scalar(select(func.count()).select_from(SalesHistory).where(*filters)) or 0
    if count > 50000:
        evidence.warnings.append(
            "Backtest input exceeds the assistant's 50,000-row safety budget. "
            "Select a product/store or narrower horizon; no partial backtest "
            "was used."
        )
        return
    try:
        result = run_backtest(
            db, cutoff, horizon, product_id=context.product_id, store_id=context.store_id
        )
    except ValueError:
        evidence.warnings.append(
            "Backtest unavailable for this scope: training or holdout dates "
            "are missing. Select an earlier historical cutoff with recorded "
            "actuals."
        )
        return
    for name, metrics in result["models"].items():
        mae = "unavailable" if metrics["mae"] is None else str(metrics["mae"])
        wape = (
            "unavailable" if metrics["wape_percent"] is None else str(metrics["wape_percent"]) + "%"
        )
        evidence.add(
            (
                f"Historical backtest {name}: cutoff {cutoff}, holdout "
                f"{result['holdout_start']} to {result['holdout_end']}; "
                f"MAE {mae} units, WAPE {wape}, coverage {metrics['coverage_percent']}%, "
                f"status {metrics['evaluation_status']}, matched "
                f"{metrics['evaluated_predictions']}, unmatched "
                f"{metrics['unmatched_predictions']}. This is a "
                f"new nonpersisted holdout calculation, not the "
                f"selected run's evaluation."
            ),
            AssistantSource(
                id="",
                type="backtest",
                label=f"Backtest baseline: {name}",
                product_id=context.product_id,
                store_id=context.store_id,
                start_date=result["holdout_start"],
                end_date=result["holdout_end"],
            ),
            metrics,
        )
    evidence.warnings.extend(result["assumptions"])
    evidence.warnings.append(
        "Compare error metrics only alongside coverage and matched "
        "samples. Lower error on unequal samples does not establish a "
        "better model. No result guarantees future accuracy."
    )
