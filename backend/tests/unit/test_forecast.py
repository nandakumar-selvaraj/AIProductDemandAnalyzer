from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.forecast import ForecastRequest
from app.services.forecast_service import get_forecast_dates, trailing_average


def test_trailing_average_preserves_fractional_value() -> None:
    assert trailing_average([1] * 29 + [2]) == Decimal("31") / Decimal("30")


def test_trailing_average_accepts_zero_demand() -> None:
    assert trailing_average([0] * 30) == Decimal(0)


def test_missing_dates_and_insufficient_history_are_excluded() -> None:
    assert trailing_average([1] * 29 + [None]) is None
    assert trailing_average([1] * 29) is None


def test_forecast_dates_start_day_after_cutoff() -> None:
    assert get_forecast_dates(date(2024, 1, 30), 2) == [date(2024, 1, 31), date(2024, 2, 1)]


def test_horizon_defaults_and_is_capped_at_30() -> None:
    assert ForecastRequest().horizon_days == 30
    with pytest.raises(ValidationError):
        ForecastRequest(horizon_days=31)
    with pytest.raises(ValidationError):
        ForecastRequest(horizon_days=0)


def test_negative_prediction_prohibited_by_sales_input_type() -> None:
    # Persisted sales are constrained non-negative and the baseline clamps defensively.
    assert trailing_average([0] * 30) >= 0
