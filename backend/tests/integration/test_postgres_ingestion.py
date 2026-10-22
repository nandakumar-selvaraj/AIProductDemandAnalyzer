"""Opt-in PostgreSQL integration checks; requires a dedicated *_test database."""

import os

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models import Product, SalesHistory, Store
from app.services.ingestion_service import ingest_sales

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="Set TEST_DATABASE_URL to a dedicated PostgreSQL *_test database"
)


def test_sales_upsert_is_repeatable_and_updates_existing_records() -> None:
    assert TEST_DATABASE_URL is not None
    database_name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0]
    if not database_name.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end in _test")
    engine = create_engine(TEST_DATABASE_URL)
    payload = b"date,store,item,sales\n2013-01-01,1,2,10\n"
    try:
        with Session(engine) as session:
            first = ingest_sales(payload, session)
            second = ingest_sales(payload, session)
            changed = ingest_sales(payload.replace(b",10", b",12"), session)
            assert first.inserted == 1
            assert second.inserted == 0 and second.updated == 1
            assert changed.updated == 1
            assert session.scalar(select(func.count()).select_from(Store)) == 1
            assert session.scalar(select(func.count()).select_from(Product)) == 1
            sale = session.scalar(select(SalesHistory))
            assert sale is not None and sale.units_sold == 12
    finally:
        engine.dispose()
