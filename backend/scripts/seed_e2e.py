"""Opt-in deterministic synthetic E2E fixture. Refuses nonempty/non-test databases."""

import os
from datetime import date, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models import ForecastRun, Product, ProductForecast, SalesHistory, Store
from app.services.forecast_service import create_forecast
from app.services.ingestion_service import ingest_sales


def main() -> None:
    # Require an explicit process environment value; never fall back to the local .env.
    raw_url = os.environ.get("DATABASE_URL", "")
    if os.environ.get("E2E_ALLOW_SEED") != "1" or not raw_url:
        raise SystemExit("Set E2E_ALLOW_SEED=1 and an explicit DATABASE_URL for an empty E2E DB")
    url = make_url(raw_url)
    if (
        url.get_backend_name() != "postgresql"
        or not (url.database or "").endswith("_e2e_test")
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise SystemExit("Seed requires a loopback PostgreSQL database ending in _e2e_test")

    engine = create_engine(url)
    try:
        with Session(engine) as session:
            for model in (Store, Product, SalesHistory, ForecastRun, ProductForecast):
                if session.scalar(select(func.count()).select_from(model)):
                    raise SystemExit("Seed refused: E2E database must be empty; nothing was reset")
            session.rollback()
            lines = ["date,store,item,sales"]
            for offset in range(91):
                day = date(2024, 1, 1) + timedelta(days=offset)
                for store in (1, 2):
                    for product in (1, 2):
                        units = 10 + store * 3 + product * 2 + offset % 7
                        lines.append(f"{day},{store},{product},{units}")
            result = ingest_sales(("\n".join(lines) + "\n").encode(), session)
            assert result.inserted == 364
            run = create_forecast(session, 7, date(2024, 2, 29))
            assert run.status == "completed"
            print("Synthetic E2E fixture ready: 364 sales rows, 4 series, 28 predictions")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
