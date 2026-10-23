from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import ForecastRun, Product, Store
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
