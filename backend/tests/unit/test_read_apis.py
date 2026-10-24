from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.endpoints.dashboard import get_dashboard_summary
from app.db.base import Base
from app.models import ForecastRun, Product, ProductForecast, SalesHistory, Store
from app.services.forecast_service import get_forecast_runs, get_latest_completed_forecast
from app.services.reporting_service import list_catalog


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_product_and_store_search_pagination(session: Session) -> None:
    session.add_all(
        [
            Product(id=1, item_code="ITEM_A", name="Apples"),
            Product(id=2, item_code="ITEM_B", name="Bananas"),
            Store(id=1, store_code="STORE_A", name="North"),
            Store(id=2, store_code="STORE_B", name="South"),
        ]
    )
    session.commit()
    product_total, products = list_catalog(session, "products", 1, 1, "Ban")
    store_total, stores = list_catalog(session, "stores", 1, 1, "south")
    assert product_total == 1 and products[0].item_code == "ITEM_B"
    assert store_total == 1 and stores[0].store_code == "STORE_B"


def test_forecast_run_listing_status_and_latest_completed(session: Session) -> None:
    session.add_all(
        [
            ForecastRun(
                id=1,
                model_name="base",
                training_cutoff=date(2024, 1, 1),
                horizon_days=30,
                status="completed",
                completed_at=datetime(2024, 2, 1, tzinfo=UTC),
            ),
            ForecastRun(
                id=2,
                model_name="base",
                training_cutoff=date(2024, 1, 2),
                horizon_days=30,
                status="failed",
            ),
        ]
    )
    session.commit()
    total, rows = get_forecast_runs(session, 1, 10, "failed")
    assert total == 1 and rows[0].id == 2
    assert get_latest_completed_forecast(session).id == 1


@pytest.mark.parametrize(
    ("history_days", "forecast_units", "expected_category"),
    [(30, 15, "increase"), (30, 10, "maintain"), (30, 5, "reduce"), (0, 15, "insufficient_data")],
)
def test_dashboard_summary_with_completed_forecast(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    history_days: int,
    forecast_units: int,
    expected_category: str,
) -> None:
    cutoff = date(2024, 1, 30)
    session.add_all(
        [
            Product(id=1, item_code="ITEM_A", name="Apples"),
            Store(id=1, store_code="STORE_A", name="North"),
            ForecastRun(
                id=1,
                model_name="base",
                training_cutoff=cutoff,
                horizon_days=1,
                status="completed",
            ),
            ProductForecast(
                id=1,
                forecast_run_id=1,
                store_id=1,
                product_id=1,
                forecast_date=cutoff + timedelta(days=1),
                predicted_units=Decimal(forecast_units),
            ),
        ]
    )
    session.add_all(
        SalesHistory(
            id=day + 1,
            store_id=1,
            product_id=1,
            sale_date=cutoff - timedelta(days=day),
            units_sold=10,
        )
        for day in range(history_days)
    )
    session.commit()
    execute = session.execute

    def execute_dashboard_query(statement, *args, **kwargs):
        # SQLite lacks date_trunc; execute the forecast aggregates and joins as real SQL.
        if "date_trunc(" in str(statement):
            monthly = [(date(2024, 1, 1), history_days * 10)] if history_days else []
            return SimpleNamespace(all=lambda: monthly)
        return execute(statement, *args, **kwargs)

    monkeypatch.setattr(session, "execute", execute_dashboard_query)
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(
            recommendation_increase_threshold_percent=Decimal("10"),
            recommendation_reduce_threshold_percent=Decimal("-10"),
        ),
    )

    summary = get_dashboard_summary(session)

    assert summary.product_count == summary.store_count == 1
    assert summary.total_units_sold == history_days * 10
    assert summary.latest_forecast is not None
    assert summary.latest_forecast.forecast_run_id == 1
    assert summary.latest_forecast.forecast_demand_total == forecast_units
    assert summary.latest_forecast.recommendation_counts == {
        category: int(category == expected_category)
        for category in ("increase", "maintain", "reduce", "insufficient_data")
    }
