"""Validate or ingest the Kaggle train.csv file."""

import argparse
import json
import sys
from pathlib import Path

# Running this file directly puts scripts/ on sys.path, not the backend root.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine, get_session_factory
from app.services.ingestion_service import ingest_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("data/raw/train.csv"),
        help="CSV path (relative to backend/ by default)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Rows per database batch",
    )
    parser.add_argument(
        "--validate-only",
        "--dry-run",
        action="store_true",
        help="Validate without connecting to PostgreSQL",
    )
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    try:
        session = None
        if not args.validate_only:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
            session = get_session_factory()()
        try:
            summary = ingest_file(
                args.file,
                session,
                validation_only=args.validate_only,
                batch_size=args.batch_size,
            )
            print(summary.model_dump_json(indent=2))
            return 1 if summary.rejected else 0
        finally:
            if session is not None:
                session.close()
    except (OSError, SQLAlchemyError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
