from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Product, SalesHistory, Store
from app.services.backtest_service import run_backtest


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_backtest_returns_two_models_and_holdout_metrics(session: Session) -> None:
    session.add_all(
        [Store(id=1, store_code="S1", name="Store"), Product(id=1, item_code="P1", name="Item")]
    )
    cutoff = date(2024, 3, 30)
    row_id = 1
    for i in range(30):
        day = cutoff - timedelta(days=29 - i)
        session.add(SalesHistory(id=row_id, store_id=1, product_id=1, sale_date=day, units_sold=10))
        row_id += 1
    for i in range(1, 3):
        session.add(
            SalesHistory(
                id=row_id,
                store_id=1,
                product_id=1,
                sale_date=cutoff + timedelta(days=i),
                units_sold=20,
            )
        )
        row_id += 1
    session.commit()

    result = run_backtest(session, cutoff, 2)
    assert set(result["models"]) == {"trailing_average", "seasonal_naive"}
    assert result["models"]["trailing_average"]["mae"] == 10
    assert result["models"]["seasonal_naive"]["mae"] == 10
    assert result["models"]["trailing_average"]["total_predicted_units"] == 20
    assert result["models"]["seasonal_naive"]["total_predicted_units"] == 20
    assert result["holdout_start"] == cutoff + timedelta(days=1)


def test_backtest_rejects_missing_global_holdout_date(session: Session) -> None:
    session.add_all(
        [Store(id=1, store_code="S1", name="Store"), Product(id=1, item_code="P1", name="Item")]
    )
    cutoff = date(2024, 3, 30)
    for i in range(30):
        day = cutoff - timedelta(days=29 - i)
        session.add(SalesHistory(id=i + 1, store_id=1, product_id=1, sale_date=day, units_sold=10))
    session.add(
        SalesHistory(
            id=31, store_id=1, product_id=1, sale_date=cutoff + timedelta(days=1), units_sold=10
        )
    )
    session.commit()
    with pytest.raises(ValueError, match="cover every date"):
        run_backtest(session, cutoff, 2)
