from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import ForecastRun, Product, ProductForecast, SalesHistory, Store
from app.services.recommendation_service import get_recommendations, recommendation_for_series


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def seed(session: Session, *, status: str = "completed", horizon: int = 2) -> ForecastRun:
    run = ForecastRun(
        id=1,
        model_name="baseline",
        training_cutoff=date(2024, 1, 30),
        horizon_days=horizon,
        status=status,
    )
    session.add_all(
        [
            run,
            Store(id=1, store_code="S1", name="Store 1"),
            Store(id=2, store_code="S2", name="Store 2"),
            Product(id=1, item_code="P1", name="Product 1"),
            Product(id=2, item_code="P2", name="Product 2"),
        ]
    )
    session.flush()
    return run


def add_series(
    session: Session,
    store: int,
    product: int,
    *,
    hist: int,
    forecast: str,
    history_days: int = 30,
    forecast_days: int = 2,
) -> None:
    cutoff = date(2024, 1, 30)
    base_id = store * 100 + product * 10
    for offset in range(history_days):
        session.add(
            SalesHistory(
                id=base_id + offset,
                store_id=store,
                product_id=product,
                sale_date=cutoff - timedelta(days=29 - offset),
                units_sold=hist,
            )
        )
    for offset in range(forecast_days):
        session.add(
            ProductForecast(
                id=base_id + offset + 1000,
                forecast_run_id=1,
                store_id=store,
                product_id=product,
                forecast_date=cutoff + timedelta(days=offset + 1),
                predicted_units=Decimal(forecast),
            )
        )


def get_items(session: Session, page=1, page_size=50):
    return get_recommendations(session, 1, page, page_size, Decimal("10"), Decimal("-10"))


def test_increase_reduce_and_maintain_thresholds() -> None:
    assert (
        recommendation_for_series(Decimal("11"), 2, 300, 30, 2, Decimal(10), Decimal(-10))[0]
        == "increase"
    )
    assert (
        recommendation_for_series(Decimal("9"), 2, 300, 30, 2, Decimal(10), Decimal(-10))[0]
        == "reduce"
    )
    assert (
        recommendation_for_series(Decimal("10.5"), 2, 300, 30, 2, Decimal(10), Decimal(-10))[0]
        == "maintain"
    )


def test_missing_history_date_is_insufficient(session: Session) -> None:
    seed(session)
    add_series(session, 1, 1, hist=10, forecast="12", history_days=29)
    session.commit()
    _, items = get_items(session)
    assert items[0]["recommendation"] == "insufficient_data"
    assert items[0]["historical_coverage_days"] == 29


def test_zero_history_handling() -> None:
    zeros = recommendation_for_series(Decimal(0), 2, 0, 30, 2, Decimal(10), Decimal(-10))
    positive = recommendation_for_series(Decimal(1), 2, 0, 30, 2, Decimal(10), Decimal(-10))
    assert zeros[0] == "maintain" and zeros[3] == Decimal(0)
    assert positive[0] == "insufficient_data" and positive[3] is None


def test_multiple_series_are_ordered_and_paginated(session: Session) -> None:
    seed(session)
    add_series(session, 2, 1, hist=10, forecast="12")
    add_series(session, 1, 2, hist=10, forecast="8")
    session.commit()
    total, first = get_items(session, page=1, page_size=1)
    _, second = get_items(session, page=2, page_size=1)
    assert total == 2
    assert (first[0]["store_id"], first[0]["product_id"]) == (1, 2)
    assert (second[0]["store_id"], second[0]["product_id"]) == (2, 1)


def test_incomplete_forecast_horizon_is_insufficient(session: Session) -> None:
    seed(session, horizon=3)
    add_series(session, 1, 1, hist=10, forecast="12", forecast_days=2)
    session.commit()
    _, items = get_items(session)
    assert items[0]["recommendation"] == "insufficient_data"


def test_nonexistent_and_noncompleted_runs(session: Session) -> None:
    from app.api.v1.endpoints.recommendations import list_recommendations

    with pytest.raises(HTTPException) as missing:
        list_recommendations(99, 1, 50, session)
    assert missing.value.status_code == 404
    seed(session, status="running")
    with pytest.raises(HTTPException) as conflict:
        list_recommendations(1, 1, 50, session)
    assert conflict.value.status_code == 409


def test_database_error_maps_to_503_without_details(monkeypatch, session: Session) -> None:
    from sqlalchemy.exc import OperationalError

    from app.api.v1.endpoints import recommendations

    def fail(*args, **kwargs):
        raise OperationalError("SELECT private_sql", {}, Exception("secret"))

    monkeypatch.setattr(recommendations, "get_recommendations", fail)
    with pytest.raises(HTTPException) as error:
        recommendations.list_recommendations(1, 1, 50, session)
    assert error.value.status_code == 503
    assert "private_sql" not in str(error.value.detail)
    assert "secret" not in str(error.value.detail)


def test_invalid_threshold_settings_are_rejected() -> None:
    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql://user:pass@localhost/db",
            recommendation_increase_threshold_percent=-1,
        )
