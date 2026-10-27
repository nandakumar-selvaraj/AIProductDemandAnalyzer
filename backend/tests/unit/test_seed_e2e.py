"""Seeding safety checks must never open the normal application database."""

from unittest.mock import MagicMock

import pytest

from scripts import seed_e2e


@pytest.mark.parametrize(
    ("permission", "url"),
    [
        ("0", "postgresql+psycopg://localhost/synthetic_e2e_test"),
        ("1", ""),
        ("1", "postgresql+psycopg://localhost/normal_database"),
        ("1", "postgresql+psycopg://remote.invalid/synthetic_e2e_test"),
        ("1", "sqlite:///synthetic_e2e_test"),
    ],
)
def test_seed_rejects_unsafe_configuration_before_connecting(monkeypatch, permission, url):
    monkeypatch.setenv("E2E_ALLOW_SEED", permission)
    monkeypatch.setenv("DATABASE_URL", url)
    engine = MagicMock(side_effect=AssertionError("Unsafe configuration opened a connection"))
    monkeypatch.setattr(seed_e2e, "create_engine", engine)
    with pytest.raises(SystemExit):
        seed_e2e.main()
    engine.assert_not_called()


def test_seed_refuses_nonempty_database_without_ingesting_or_resetting(monkeypatch):
    monkeypatch.setenv("E2E_ALLOW_SEED", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/synthetic_e2e_test")
    engine = MagicMock()
    session = MagicMock()
    session.scalar.return_value = 1
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    ingestion = MagicMock()
    monkeypatch.setattr(seed_e2e, "create_engine", MagicMock(return_value=engine))
    monkeypatch.setattr(seed_e2e, "Session", session_factory)
    monkeypatch.setattr(seed_e2e, "ingest_sales", ingestion)
    with pytest.raises(SystemExit, match="must be empty"):
        seed_e2e.main()
    ingestion.assert_not_called()
    engine.dispose.assert_called_once()
