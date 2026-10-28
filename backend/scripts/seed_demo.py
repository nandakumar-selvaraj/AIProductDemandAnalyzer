"""Seed only an explicitly opted-in, empty *_demo database; never reset data."""

import os
import re
from datetime import date, timedelta

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import DEMO_MARKER
from app.services.forecast_service import create_forecast
from app.services.ingestion_service import ingest_sales


def main():
    raw = os.environ.get("DATABASE_URL", "")
    if os.environ.get("DEMO_ALLOW_SEED") != "1" or not raw:
        raise SystemExit("Explicit DEMO_ALLOW_SEED=1 and DATABASE_URL are required")
    url = make_url(raw)
    name = url.database or ""
    if url.get_backend_name() != "postgresql" or not re.fullmatch(r"[a-z0-9_]+_demo", name):
        raise SystemExit("Only a dedicated lowercase *_demo database may be seeded")
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            # Reject any existing application records, including auxiliary tables.
            for table in Base.metadata.sorted_tables:
                if session.execute(select(table).limit(1)).first() is not None:
                    raise SystemExit("Database must be empty; no data was changed")
            session.rollback()
            rows = ["date,store,item,sales"]
            for offset in range(91):
                day = date(2024, 1, 1) + timedelta(days=offset)
                for store in (1, 2):
                    for item in (1, 2):
                        rows.append(
                            f"{day},{store},{item},{10 + store * 3 + item * 2 + offset % 7}"
                        )
            ingest_sales(("\n".join(rows) + "\n").encode(), session)
            run = create_forecast(session, 7, date(2024, 2, 29))
            if run.status != "completed":
                raise RuntimeError("Synthetic forecast did not complete")
            # A failed/partial seed is never advertised as a verified demo dataset.
            session.execute(text(f"COMMENT ON DATABASE \"{name}\" IS '{DEMO_MARKER}'"))
            session.commit()
        print("Synthetic-v1 demo initialized: 364 sales rows, 28 predictions")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
