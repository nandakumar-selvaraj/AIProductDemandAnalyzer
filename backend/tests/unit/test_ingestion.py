from app.core.exceptions import IngestionValidationError
from app.services.ingestion_service import ingest_sales, validate_csv


def test_parses_expected_rows(kaggle_csv: bytes) -> None:
    rows, issues, count, duplicates = validate_csv(kaggle_csv)
    assert len(rows) == 2
    assert not issues
    assert count == 2
    assert duplicates == 0
    assert rows[0]["store_code"] == "STORE_1"
    assert rows[0]["item_code"] == "ITEM_2"


def test_reports_invalid_values_and_duplicate_keys() -> None:
    csv = b"date,store,item,sales\n2013-01-01,1,2,10\n2013-01-01,1,2,12\nnope,1,2,-1\n"
    rows, issues, count, duplicates = validate_csv(csv)
    assert len(rows) == 1 and rows[0]["units_sold"] == 12
    assert count == 3 and duplicates == 1
    assert len(issues) == 1 and issues[0].row == 4


def test_rejects_missing_columns() -> None:
    try:
        validate_csv(b"date,store\n2013-01-01,1\n")
    except IngestionValidationError as exc:
        assert "date, store, item, and sales" in str(exc)
    else:
        raise AssertionError("missing columns were accepted")


def test_validation_only_summary(kaggle_csv: bytes) -> None:
    result = ingest_sales(kaggle_csv, None, validation_only=True)
    assert result.records_read == 2
    assert result.inserted == result.updated == 0
    assert result.validation_only
