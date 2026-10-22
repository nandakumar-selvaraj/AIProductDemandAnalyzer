"""CSV validation and transaction-safe Kaggle sales ingestion."""

import csv
import io
import logging
import re
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import IngestionValidationError
from app.repositories.ingestion_repository import persist_sales
from app.schemas.ingestion import IngestionSummary, RowIssue

logger = logging.getLogger(__name__)
EXPECTED_COLUMNS = {"date", "store", "item", "sales"}
IDENTIFIER = re.compile(r"[0-9]+\Z")


def validate_csv(content: bytes) -> tuple[list[dict[str, object]], list[RowIssue], int, int]:
    """Parse source CSV, retaining row-level errors rather than dropping them silently."""
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise IngestionValidationError("CSV must be a well-formed UTF-8 file") from exc
    if reader.fieldnames is None or not EXPECTED_COLUMNS.issubset(
        {name.strip() for name in reader.fieldnames}
    ):
        raise IngestionValidationError("CSV must include date, store, item, and sales columns")
    reader.fieldnames = [name.strip() for name in reader.fieldnames]
    accepted: dict[tuple[date, int, int], dict[str, object]] = {}
    issues: list[RowIssue] = []
    records_read = duplicates = 0
    line = 1
    while True:
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            issues.append(RowIssue(row=records_read + 2, reason=f"malformed CSV: {exc}"))
            break
        line += 1
        records_read += 1
        try:
            if None in row or any(
                row.get(col) is None or not row[col].strip() for col in EXPECTED_COLUMNS
            ):
                raise ValueError("missing required value or malformed row")
            store_raw, item_raw, sales_raw = (
                row["store"].strip(),
                row["item"].strip(),
                row["sales"].strip(),
            )
            if not IDENTIFIER.fullmatch(store_raw) or not IDENTIFIER.fullmatch(item_raw):
                raise ValueError("store and item must be non-negative integer identifiers")
            if not IDENTIFIER.fullmatch(sales_raw):
                raise ValueError("sales must be a non-negative integer")
            sale_date = date.fromisoformat(row["date"].strip())
            store_id, item_id, sales = int(store_raw), int(item_raw), int(sales_raw)
            key = (sale_date, store_id, item_id)
            record = {
                "sale_date": sale_date,
                "store_code": f"STORE_{store_id}",
                "item_code": f"ITEM_{item_id}",
                "units_sold": sales,
            }
            if key in accepted:
                duplicates += 1
            accepted[key] = record
        except (ValueError, AttributeError) as exc:
            issues.append(RowIssue(row=line, reason=str(exc)))
    return list(accepted.values()), issues, records_read, duplicates


def ingest_sales(
    content: bytes,
    session: Session | None,
    *,
    validation_only: bool = False,
    batch_size: int = 1000,
) -> IngestionSummary:
    records, issues, read_count, duplicates = validate_csv(content)
    inserted = updated = 0
    if not validation_only and records:
        if session is None:
            raise ValueError("A database session is required unless validation_only is true")
        try:
            inserted, updated = persist_sales(session, records, batch_size=batch_size)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Sales ingestion transaction failed")
            raise
    return IngestionSummary(
        records_read=read_count,
        inserted=inserted,
        updated=updated,
        rejected=len(issues),
        skipped=duplicates,
        validation_only=validation_only,
        issues=issues[:100],
    )


def ingest_file(
    path: Path,
    session: Session | None,
    *,
    validation_only: bool = False,
    batch_size: int = 1000,
) -> IngestionSummary:
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")
    return ingest_sales(
        path.read_bytes(), session, validation_only=validation_only, batch_size=batch_size
    )
