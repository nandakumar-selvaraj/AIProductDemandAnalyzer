from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import ForecastRun, Product, ProductForecast, Store


@pytest.fixture
def client_and_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    def override_get_db():
        with Session(engine) as request_session:
            yield request_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), session
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def create_run(session: Session) -> ForecastRun:
    run = ForecastRun(
        id=1,
        model_name="test",
        training_cutoff=date(2024, 1, 1),
        horizon_days=30,
        status="completed",
    )
    session.add_all(
        [
            run,
            Store(id=1, store_code="S1", name="Store 1"),
            Store(id=2, store_code="S2", name="Store 2"),
            Product(id=1, item_code="P1", name="Product 1"),
        ]
    )
    session.flush()
    return run


def test_pagination_order_and_page_beyond_end(client_and_session) -> None:
    client, session = client_and_session
    run = create_run(session)
    session.add_all(
        [
            ProductForecast(
                id=1,
                forecast_run_id=run.id,
                store_id=2,
                product_id=1,
                forecast_date=date(2024, 1, 2),
                predicted_units=Decimal("2.5"),
            ),
            ProductForecast(
                id=2,
                forecast_run_id=run.id,
                store_id=1,
                product_id=1,
                forecast_date=date(2024, 1, 1),
                predicted_units=Decimal("1"),
            ),
            ProductForecast(
                id=3,
                forecast_run_id=run.id,
                store_id=1,
                product_id=1,
                forecast_date=date(2024, 1, 2),
                predicted_units=Decimal("3"),
            ),
        ]
    )
    session.commit()

    first = client.get(f"/api/v1/forecasts/{run.id}/predictions?page=1&page_size=2")
    assert first.status_code == 200
    body = first.json()
    assert (body["total_records"], body["total_pages"]) == (3, 2)
    assert (body["run_id"], body["page"], body["page_size"]) == (run.id, 1, 2)
    assert body["items"][0] == {
        "id": 2,
        "forecast_run_id": run.id,
        "store_id": 1,
        "product_id": 1,
        "forecast_date": "2024-01-01",
        "predicted_units": "1.000",
    }
    assert [(item["forecast_date"], item["store_id"]) for item in body["items"]] == [
        ("2024-01-01", 1),
        ("2024-01-02", 1),
    ]
    beyond = client.get(f"/api/v1/forecasts/{run.id}/predictions?page=9")
    assert beyond.status_code == 200 and beyond.json()["items"] == []


def test_missing_run_and_empty_run(client_and_session) -> None:
    client, session = client_and_session
    run = create_run(session)
    session.commit()
    missing = client.get("/api/v1/forecasts/999/predictions")
    assert missing.status_code == 404
    empty = client.get(f"/api/v1/forecasts/{run.id}/predictions")
    assert empty.status_code == 200
    assert empty.json()["total_records"] == empty.json()["total_pages"] == 0
    assert empty.json()["items"] == []


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/forecasts/0/predictions",
        "/api/v1/forecasts/nope/predictions",
        "/api/v1/forecasts/1/predictions?page=0",
        "/api/v1/forecasts/1/predictions?page_size=0",
        "/api/v1/forecasts/1/predictions?page_size=501",
    ],
)
def test_invalid_parameters_return_422(client_and_session, url: str) -> None:
    client, _ = client_and_session
    assert client.get(url).status_code == 422


def test_database_failure_returns_safe_503(monkeypatch) -> None:
    from sqlalchemy.exc import OperationalError

    from app.api.v1.endpoints import forecasts

    def fail(*args, **kwargs):
        raise OperationalError("SELECT secret", {}, Exception("private"))

    monkeypatch.setattr(forecasts, "get_forecast_predictions", fail)
    engine = create_engine("sqlite://")
    session = Session(engine)
    app.dependency_overrides[get_db] = lambda: session
    try:
        response = TestClient(app).get("/api/v1/forecasts/1/predictions")
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()
    assert response.status_code == 503
    assert "secret" not in response.text and "private" not in response.text
