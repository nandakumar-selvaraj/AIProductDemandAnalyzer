"""Database engine factory and FastAPI session dependency."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create the pooled engine lazily; importing the app does not connect."""
    return create_engine(
        str(get_settings().database_url),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=2,
        pool_timeout=10,
        connect_args={"options": "-c statement_timeout=30000"},
    )


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
