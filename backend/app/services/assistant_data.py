"Allowlisted bounded reads and deterministic statements; the model has no DB connection."

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import ForecastRun, Product, ProductForecast, SalesHistory, Store
from app.schemas.assistant import AssistantContext, AssistantSource, Intent
from app.services.assistant_aggregates import (
    backtest_evidence,
    forecast_stores,
    historical_aggregate,
)
from app.services.assistant_conversations import AssistantError
from app.services.forecast_service import evaluate_forecast, get_latest_completed_forecast
from app.services.recommendation_service import get_recommendations
from app.services.reporting_service import product_analytics

GENERAL = {
    "baseline": (
        "Forecasts use a trailing average over thirty calendar dates "
        "through the training cutoff. Only series with every training date "
        "recorded are included. Predictions begin the next date and cover "
        "the selected horizon. This baseline has no seasonality, trend or "
        "uncertainty model."
    ),
    "evaluation": (
        "MAE is the mean absolute prediction error among matched actual "
        "sales. WAPE divides summed absolute error by matched actual units "
        "and expresses the result as a percentage. WAPE is unavailable "
        "when there are no matches or matched actual units sum to zero. "
        "Coverage measures matching data, not model quality."
    ),
    "recommendations": (
        "Demand recommendations compare forecast daily average with the "
        "historical calendar-day average over a complete training window. "
        "Incomplete history or forecast horizons produce insufficient "
        "data. Signals do not estimate inventory or purchase quantities."
    ),
    "scope": (
        "Historical sales are recorded observations; forecasts are "
        "estimates. Missing dates are not zero sales. A cutoff is the last "
        "training date, not the first prediction date. Forecasts are never "
        "guaranteed."
    ),
}


@dataclass
class Evidence:
    facts: list[dict[str, object]] = field(default_factory=list)
    sources: list[AssistantSource] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(self, text: str, source: AssistantSource, values: dict | None = None):
        key = f"f{len(self.facts) + 1}"
        source.id = key
        self.facts.append(
            {
                "id": key,
                "text": text,
                "values": safe_values({**source.model_dump(mode="json"), **(values or {})}),
            }
        )
        self.sources.append(source)


def metric(value) -> str:
    return "unavailable" if value is None else str(value)


def safe_values(value):
    if isinstance(value, (date, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {key: safe_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [safe_values(item) for item in value]
    return value


def retrieve(
    db: Session, intent: Intent, context: AssistantContext, question: str, settings: Settings
) -> Evidence:
    evidence = Evidence()
    limit = settings.ai_max_context_records
    if intent == "general":
        for key, text in GENERAL.items():
            evidence.add(
                text, AssistantSource(id="", type="application", label=f"Application rules: {key}")
            )
        evidence.warnings.append(
            "Application explanation only; no dataset-specific finding is claimed."
        )
        return evidence
    for name, model in [("product_id", Product), ("store_id", Store)]:
        value = getattr(context, name)
        if value is not None and db.get(model, value) is None:
            raise AssistantError(
                "record_not_found", f"The selected {name.removesuffix('_id')} was not found.", 404
            )
    if intent == "historical":
        if context.product_id is None:
            historical_aggregate(db, context, question, limit, evidence)
            return evidence
        if "declin" in question.lower() or "decreas" in question.lower():
            historical_aggregate(db, context, question, limit, evidence)
            return evidence
        result = product_analytics(
            db, context.product_id, context.store_id, context.start_date, context.end_date
        )
        if result is None:
            raise AssistantError("record_not_found", "Product was not found.", 404)
        summary, daily, monthly = result
        if not summary[3]:
            evidence.warnings.append(
                "No recorded sales observations match this product, store and date "
                "scope. Missing sales are not zero demand."
            )
            return evidence
        source = dict(
            type="historical",
            product_id=context.product_id,
            store_id=context.store_id,
            start_date=summary[0],
            end_date=summary[1],
        )
        evidence.add(
            (
                f"Product #{context.product_id}, "
                f"{('store #' + str(context.store_id)) if context.store_id else 'all stores'}: "
                f"{summary[2]} recorded units across {summary[3]} observed "
                f"sales dates from {summary[0]} to {summary[1]}. Observed "
                f"dates are not calendar days. "
                f"Average per observed date: {Decimal(summary[2]) / summary[3]} units."
            ),
            AssistantSource(id="", label="Historical sales summary", **source),
            {
                "total_units": summary[2],
                "observed_dates": summary[3],
                "average_per_observed_date": Decimal(summary[2]) / summary[3],
            },
        )
        if "across stores" in question.lower() or "compare stores" in question.lower():
            filters = [
                SalesHistory.product_id == context.product_id,
                SalesHistory.sale_date.between(summary[0], summary[1]),
            ]
            if context.store_id:
                filters.append(SalesHistory.store_id == context.store_id)
            rows = db.execute(
                select(
                    SalesHistory.store_id,
                    func.sum(SalesHistory.units_sold),
                    func.count(func.distinct(SalesHistory.sale_date)),
                )
                .where(*filters)
                .group_by(SalesHistory.store_id)
                .order_by(SalesHistory.store_id)
                .limit(limit)
            ).all()
            for store, total, dates in rows[: limit - 1]:
                evidence.add(
                    (
                        f"Store #{store}: {total} recorded units across {dates} "
                        f"observed dates for product #{context.product_id} in "
                        f"the observed report range."
                    ),
                    AssistantSource(
                        id="", label="Store historical aggregate", **{**source, "store_id": store}
                    ),
                )
            evidence.warnings.append(
                f"Store comparison shows at most {limit - 1} stores in "
                f"store-ID order; not necessarily exhaustive."
            )
        else:
            for month, total in monthly[: limit - 1]:
                evidence.add(
                    (
                        f"Recorded monthly total for {month}: {total} units for "
                        f"this historical scope. Edge months may be partial."
                    ),
                    AssistantSource(id="", label=f"Historical month {month}", **source),
                )
        evidence.warnings.append(
            "Historical analytics is bounded to at most 365 inclusive calendar "
            "days. Missing dates are not filled."
        )
        return evidence
    if intent == "backtest":
        backtest_evidence(db, context, evidence)
        return evidence
    run = (
        db.get(ForecastRun, context.forecast_run_id)
        if context.forecast_run_id
        else get_latest_completed_forecast(db)
    )
    if run is None:
        if context.forecast_run_id:
            raise AssistantError("record_not_found", "Forecast run was not found.", 404)
        evidence.warnings.append("No completed forecast run is available.")
        return evidence
    if run.status != "completed":
        raise AssistantError("forecast_not_completed", "Select a completed forecast run.", 409)
    context.forecast_run_id = run.id
    common = dict(
        forecast_run_id=run.id,
        start_date=run.training_cutoff + timedelta(days=1),
        end_date=run.training_cutoff + timedelta(days=run.horizon_days),
    )
    evidence.warnings.append(
        "Predicted demand is not actual sales, a guarantee, inventory on "
        "hand or a purchase quantity."
    )
    if intent == "evaluation":
        result = evaluate_forecast(db, run.id)
        assert result is not None
        data = result[1]
        evidence.add(
            (
                f"Run #{run.id} evaluation: status {data['evaluation_status']}; "
                f"{data['evaluated_predictions']} evaluated and {data['unmatched_predictions']} "
                f"unmatched out of {data['total_predictions']} predictions; "
                f"matching coverage {metric(data['coverage_percent'])}%; "
                f"MAE {metric(data['mae'])} units; "
                f"WAPE {metric(data['wape_percent'])}"
                f"{'%' if data['wape_percent'] is not None else ''}; "
                f"matched actual units {data['total_actual_units']}; "
                f"matched predicted units {metric(data['total_predicted_units'])}."
            ),
            AssistantSource(id="", type="evaluation", label="Persisted-run evaluation", **common),
            data,
        )
        evidence.warnings.append(
            "Evaluation covers the entire selected run, not a product/store "
            "subset. Errors describe matched actuals only; partial/unavailable "
            "coverage limits conclusions."
        )
        return evidence
    if intent == "recommendations":
        result = get_recommendations(
            db,
            run.id,
            1,
            100,
            settings.recommendation_increase_threshold_percent,
            settings.recommendation_reduce_threshold_percent,
            context.product_id,
            context.store_id,
        )
        assert result is not None
        total, rows = result
        page = 1
        while len(rows) < min(total, settings.ai_max_retrieval_series):
            page += 1
            more = get_recommendations(
                db,
                run.id,
                page,
                100,
                settings.recommendation_increase_threshold_percent,
                settings.recommendation_reduce_threshold_percent,
                context.product_id,
                context.store_id,
            )
            if more is None or more[0] != total or not more[1]:
                evidence.warnings.append(
                    "Recommendation data changed during retrieval; scope may be incomplete."
                )
                break
            rows.extend(more[1])
        rows = rows[: settings.ai_max_retrieval_series]
        trend = (
            "insufficient_data"
            if "insufficient" in question.lower()
            else "reduce"
            if any(word in question.lower() for word in ["decreas", "reduc", "declin"])
            else "increase"
            if any(word in question.lower() for word in ["increas", "stocking"])
            else None
        )
        for row in rows:
            if len(evidence.facts) >= limit:
                break
            if trend and row["recommendation"] != trend:
                continue
            evidence.add(
                (
                    f"Run #{run.id}, product #{row['product_id']}, store "
                    f"#{row['store_id']}: {row['recommendation']}. Historical "
                    f"daily average {metric(row['historical_daily_average'])}; "
                    f"forecast daily average {metric(row['forecast_daily_average'])}; "
                    f"change {metric(row['change_percent'])}"
                    f"{'%' if row['change_percent'] is not None else ''}; "
                    f"history coverage {row['historical_coverage_days']}/30 "
                    f"dates from {row['historical_window_start']} through "
                    f"{row['historical_window_end']}. Reason: {row['reason']}"
                ),
                AssistantSource(
                    id="",
                    type="recommendation",
                    product_id=row["product_id"],
                    store_id=row["store_id"],
                    label="Demand-trend recommendation",
                    **common,
                ),
                row,
            )
        evidence.warnings.append(
            f"Inspected {len(rows)} of {total} matching store/product "
            f"series in ID order; this is not a whole-dataset ranking. "
            f"At most {limit} matching evidence records are sent to the model. "
            f"If inspection is incomplete, no match does not imply none elsewhere."
        )
        return evidence
    filters = [
        ProductForecast.forecast_run_id == run.id,
        ProductForecast.forecast_date.between(common["start_date"], common["end_date"]),
    ]
    if context.product_id:
        filters.append(ProductForecast.product_id == context.product_id)
    if context.store_id:
        filters.append(ProductForecast.store_id == context.store_id)
    if "across stores" in question.lower() or "compare stores" in question.lower():
        forecast_stores(db, context, run, filters, evidence, limit, common)
        return evidence
    total_units = func.sum(ProductForecast.predicted_units)
    rows = db.execute(
        select(
            ProductForecast.product_id,
            total_units,
            func.count(),
            func.count(func.distinct(ProductForecast.forecast_date)),
        )
        .where(*filters)
        .group_by(ProductForecast.product_id)
        .order_by(total_units.desc(), ProductForecast.product_id)
        .limit(limit)
    ).all()
    store_scope = f"store #{context.store_id}" if context.store_id else "all forecast stores"
    for product, units, predictions, dates in rows:
        evidence.add(
            (
                f"Run #{run.id}, product #{product}, "
                f"{store_scope}: "
                f"predicted total {Decimal(str(units))} units across "
                f"{predictions} persisted predictions and {dates} forecast "
                f"dates, {common['start_date']} to {common['end_date']}. "
                f"Model {run.model_name}; training cutoff {run.training_cutoff}. "
                f"This total is computed from all matching persisted "
                f"prediction rows, not one page."
            ),
            AssistantSource(
                id="",
                type="forecast",
                label="Persisted prediction aggregate",
                product_id=product,
                store_id=context.store_id,
                **common,
            ),
            {
                "predicted_total": Decimal(str(units)),
                "persisted_predictions": predictions,
                "forecast_dates": dates,
            },
        )
    evidence.warnings.append(
        f"At most {limit} products are retrieved, ordered by "
        f"full scoped predicted totals descending. Totals cover "
        f"persisted observations only, not a guarantee of complete "
        f"store coverage."
    )
    return evidence
