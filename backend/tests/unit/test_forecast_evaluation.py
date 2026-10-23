from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import ForecastRun, Product, ProductForecast, SalesHistory, Store
from app.schemas.forecast import ForecastEvaluationRequest
from app.services.forecast_service import evaluate_forecast


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def seed_run(session: Session, status: str = "completed") -> ForecastRun:
    run = ForecastRun(
        id=1,
        model_name="baseline",
        training_cutoff=date(2024, 1, 1),
        horizon_days=2,
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


def add_prediction(
    session: Session, row_id: int, store: int, product: int, day: int, predicted: str
):
    session.add(
        ProductForecast(
            id=row_id,
            forecast_run_id=1,
            store_id=store,
            product_id=product,
            forecast_date=date(2024, 1, day),
            predicted_units=Decimal(predicted),
        )
    )


def add_actual(session: Session, row_id: int, store: int, product: int, day: int, actual: int):
    session.add(
        SalesHistory(
            id=row_id,
            store_id=store,
            product_id=product,
            sale_date=date(2024, 1, day),
            units_sold=actual,
        )
    )


def test_evaluation_metrics_include_multiple_store_product_series(session: Session) -> None:
    seed_run(session)
    add_prediction(session, 1, 1, 1, 2, "12")
    add_prediction(session, 2, 2, 2, 3, "8")
    add_actual(session, 1, 1, 1, 2, 10)
    add_actual(session, 2, 2, 2, 3, 10)
    session.commit()

    run, result = evaluate_forecast(session, 1)
    assert run.id == 1
    assert result == {
        "total_predictions": 2,
        "evaluated_predictions": 2,
        "unmatched_predictions": 0,
        "coverage_percent": Decimal("100"),
        "total_actual_units": 20,
        "total_predicted_units": Decimal("20"),
        "mae": Decimal("2"),
        "wape_percent": Decimal("20"),
        "evaluation_status": "complete",
    }


def test_unmatched_predictions_are_reported_and_metrics_use_matches(session: Session) -> None:
    seed_run(session)
    add_prediction(session, 1, 1, 1, 2, "12")
    add_prediction(session, 2, 2, 2, 3, "8")
    add_actual(session, 1, 1, 1, 2, 10)
    session.commit()
    _, result = evaluate_forecast(session, 1)
    assert result["evaluated_predictions"] == 1
    assert result["unmatched_predictions"] == 1
    assert result["coverage_percent"] == Decimal("50")
    assert result["mae"] == Decimal("2")
    assert result["evaluation_status"] == "partial"


def test_zero_actual_returns_null_wape(session: Session) -> None:
    seed_run(session)
    add_prediction(session, 1, 1, 1, 2, "3")
    add_actual(session, 1, 1, 1, 2, 0)
    session.commit()
    _, result = evaluate_forecast(session, 1)
    assert result["mae"] == Decimal("3")
    assert result["wape_percent"] is None


def test_no_predictions_and_no_actual_matches_are_unavailable(session: Session) -> None:
    seed_run(session)
    session.commit()
    _, empty = evaluate_forecast(session, 1)
    assert empty["evaluation_status"] == "unavailable"
    assert empty["mae"] is None and empty["wape_percent"] is None

    add_prediction(session, 1, 1, 1, 2, "4")
    session.commit()
    _, unmatched = evaluate_forecast(session, 1)
    assert unmatched["evaluated_predictions"] == 0
    assert unmatched["unmatched_predictions"] == 1
    assert unmatched["evaluation_status"] == "unavailable"


def test_only_forecast_window_is_considered_and_run_status_is_enforced(session: Session) -> None:
    seed_run(session, status="running")
    with pytest.raises(ValueError, match="completed"):
        evaluate_forecast(session, 1)


def test_sales_before_cutoff_and_after_horizon_are_not_counted(session: Session) -> None:
    seed_run(session)
    add_prediction(session, 1, 1, 1, 2, "5")
    add_actual(session, 1, 1, 1, 1, 99)
    add_actual(session, 2, 1, 1, 4, 99)
    session.commit()

    _, result = evaluate_forecast(session, 1)
    assert result["total_predictions"] == 1
    assert result["evaluated_predictions"] == 0
    assert result["unmatched_predictions"] == 1
    assert result["total_actual_units"] == 0
    assert result["mae"] is None


def test_actual_with_different_store_or_product_does_not_match(session: Session) -> None:
    seed_run(session)
    add_prediction(session, 1, 1, 1, 2, "5")
    add_actual(session, 1, 2, 1, 2, 5)
    add_actual(session, 2, 1, 2, 2, 5)
    session.commit()

    _, result = evaluate_forecast(session, 1)
    assert result["evaluated_predictions"] == 0
    assert result["unmatched_predictions"] == 1
    assert result["evaluation_status"] == "unavailable"


def test_api_returns_evaluation_response_schema(session: Session) -> None:
    from app.api.v1.endpoints.forecasts import post_forecast_evaluation

    seed_run(session)
    add_prediction(session, 1, 1, 1, 2, "12")
    add_actual(session, 1, 1, 1, 2, 10)
    session.commit()

    response = post_forecast_evaluation(ForecastEvaluationRequest(forecast_run_id=1), session)
    assert response.forecast_run_id == 1
    assert response.total_predictions == 1
    assert response.evaluated_predictions == 1
    assert response.coverage_percent == Decimal("100")
    assert response.mae == Decimal("2")
    assert response.wape_percent == Decimal("20")


def test_request_validation_rejects_invalid_id_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ForecastEvaluationRequest(forecast_run_id=0)
    with pytest.raises(ValidationError):
        ForecastEvaluationRequest(forecast_run_id=1, unexpected=True)


def test_endpoint_maps_missing_run_and_incomplete_status(session: Session) -> None:
    from app.api.v1.endpoints.forecasts import post_forecast_evaluation
    from app.schemas.forecast import ForecastEvaluationRequest

    with pytest.raises(HTTPException) as missing:
        post_forecast_evaluation(ForecastEvaluationRequest(forecast_run_id=9), session)
    assert missing.value.status_code == 404
    seed_run(session, status="pending")
    with pytest.raises(HTTPException) as conflict:
        post_forecast_evaluation(ForecastEvaluationRequest(forecast_run_id=1), session)
    assert conflict.value.status_code == 409


def test_endpoint_maps_database_error_without_exposing_details(
    monkeypatch, session: Session
) -> None:
    from sqlalchemy.exc import OperationalError

    from app.api.v1.endpoints import forecasts
    from app.schemas.forecast import ForecastEvaluationRequest

    def fail(*args, **kwargs):
        raise OperationalError("SELECT private_sql", {}, Exception("secret"))

    monkeypatch.setattr(forecasts, "evaluate_forecast", fail)
    with pytest.raises(HTTPException) as error:
        forecasts.post_forecast_evaluation(ForecastEvaluationRequest(forecast_run_id=1), session)
    assert error.value.status_code == 503
    assert "private_sql" not in str(error.value.detail)
    assert "secret" not in str(error.value.detail)
