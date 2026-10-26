import asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models import SalesHistory
from app.schemas.assistant import AssistantContext, AssistantRequest, ModelSelection
from app.services.assistant_conversations import Conversation
from app.services.assistant_data import Evidence, retrieve
from app.services.assistant_service import answer, classify
from tests.unit.test_assistant import db as seed_db
from tests.unit.test_assistant import settings


@pytest.fixture(name="db")
def seeded_database():
    yield from seed_db.__wrapped__()


def test_complete_historical_ranking_and_observed_date_average(db):
    db.add(
        SalesHistory(id=99, product_id=2, store_id=1, sale_date=date(2024, 1, 30), units_sold=999)
    )
    db.commit()
    context = AssistantContext(start_date=date(2024, 1, 1), end_date=date(2024, 1, 30))
    facts = retrieve(
        db,
        "historical",
        context,
        "Which products had highest historical sales?",
        settings(ai_max_context_records=1),
    )
    assert len(facts.facts) == 1 and facts.sources[0].product_id == 2
    assert facts.facts[0]["values"]["total_units"] == 999
    assert facts.facts[0]["values"]["observed_dates"] == 1
    average = retrieve(db, "historical", context, "average daily sales", settings())
    assert average.facts[0]["values"]["average_per_observed_date"] == str(Decimal(1299) / 30)


def test_historical_decline_filters_complete_scope_without_zero_filling(db):
    for index, units in [(100, 100), (101, 1)]:
        db.add(
            SalesHistory(
                id=index,
                product_id=2,
                store_id=1,
                sale_date=date(2024, 1, 1) if index == 100 else date(2024, 1, 30),
                units_sold=units,
            )
        )
    db.commit()
    context = AssistantContext(start_date=date(2024, 1, 1), end_date=date(2024, 1, 30))
    assert classify("Which products have declining historical sales?") == "historical"
    evidence = retrieve(db, "historical", context, "declining historical sales", settings())
    assert [source.product_id for source in evidence.sources] == [2]
    assert evidence.facts[0]["values"]["first_observed_dates"] == 1
    assert evidence.facts[0]["values"]["change_percent"] == "-99.00"


def test_scoped_backtest_is_not_persisted_evaluation_and_keeps_nulls(db):
    cutoff = date(2024, 1, 30)
    db.add_all(
        SalesHistory(
            id=100 + day,
            product_id=1,
            store_id=1,
            sale_date=cutoff + timedelta(days=day),
            units_sold=10,
        )
        for day in (1, 2)
    )
    db.commit()
    context = AssistantContext(product_id=1, backtest_cutoff=cutoff, backtest_horizon_days=2)
    evidence = retrieve(
        db, "backtest", context, "Which method performed better in backtesting?", settings()
    )
    assert len(evidence.facts) == 2
    assert all(
        source.type == "backtest" and source.forecast_run_id is None for source in evidence.sources
    )
    assert evidence.facts[0]["values"]["mae"] == "0"
    assert "not the selected run's evaluation" in evidence.facts[0]["text"]
    missing = retrieve(db, "backtest", AssistantContext(), "compare backtests", settings())
    assert not missing.facts and "Choose a historical backtest cutoff" in missing.warnings[0]


def test_evaluation_structured_evidence_preserves_unavailable_null(db):
    evidence = retrieve(
        db, "evaluation", AssistantContext(forecast_run_id=1), "accuracy", settings()
    )
    assert evidence.facts[0]["values"]["mae"] is None
    assert evidence.facts[0]["values"]["wape_percent"] is None


def test_forecast_store_comparison_and_missing_product_clarification(db):
    evidence = retrieve(
        db,
        "forecast",
        AssistantContext(forecast_run_id=1, product_id=1),
        "compare forecasts across stores",
        settings(),
    )
    assert evidence.sources[0].store_id == 1
    assert evidence.facts[0]["values"]["predicted_units"] == "30.246"
    missing = retrieve(
        db,
        "forecast",
        AssistantContext(forecast_run_id=1),
        "compare forecasts across stores",
        settings(),
    )
    assert not missing.facts and "one product" in missing.warnings[-1]


def test_invalid_model_evidence_id_never_reaches_answer():
    class BadProvider:
        async def select_evidence(self, payload):
            return ModelSelection(fact_ids=["f999"])

    import pytest

    from app.schemas.assistant import AssistantSource
    from app.services.ai_provider import ProviderError

    evidence = Evidence()
    evidence.add(
        "Verified 12.345 units.", AssistantSource(id="", type="application", label="Verified rule")
    )
    with pytest.raises(ProviderError, match="unsupported evidence"):
        asyncio.run(
            answer(
                AssistantRequest(message="Explain"),
                Conversation(owner=uuid4()),
                uuid4(),
                "general",
                AssistantContext(),
                evidence,
                BadProvider(),
                settings(),
            )
        )


def test_disconnect_cancels_inference_and_releases_conversation(db):
    from fastapi import HTTPException

    from app.api.v1.endpoints.assistant import chat
    from app.services.assistant_conversations import conversations

    cancelled = []

    class RequestGone:
        async def is_disconnected(self):
            return True

    class SlowProvider:
        async def select_evidence(self, payload):
            try:
                await asyncio.sleep(60)
            finally:
                cancelled.append(True)

    owner = uuid4()
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            chat(
                AssistantRequest(message="Forecast product 1", context={"forecast_run_id": 1}),
                RequestGone(),
                owner,
                settings(),
                db,
                SlowProvider(),
            )
        )
    assert error.value.status_code == 499 and cancelled == [True]
    assert all(not row.busy for row in conversations.rows.values() if row.owner == owner)
