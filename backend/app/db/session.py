"""Database engine factory and FastAPI session dependency."""

from collections.abc import Generator
from functools import lru_cache

from fastapi import Request
from sqlalchemy import create_engine, text
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


def get_db(request: Request) -> Generator[Session]:
    factory = (
        sessionmaker(bind=get_demo_engine(), autoflush=False, expire_on_commit=False)
        if getattr(request.state, "public_demo", False)
        else get_session_factory()
    )
    session = factory()
    try:
        yield session
    finally:
        session.close()


DEMO_MARKER = "AIProductDemandAnalyzer synthetic-v1"


@lru_cache
def get_demo_engine() -> Engine:
    settings = get_settings()
    if not settings.public_demo_enabled or settings.demo_database_url is None:
        raise RuntimeError("Public demo database is not configured")
    return create_engine(
        str(settings.demo_database_url),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=1,
        pool_timeout=5,
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=5000"},
    )


def verify_demo_database() -> None:
    with get_demo_engine().connect() as connection:
        marker = connection.scalar(
            text(
                "SELECT shobj_description(oid, 'pg_database') FROM pg_database "
                "WHERE datname=current_database()"
            )
        )
        if marker != DEMO_MARKER:
            raise RuntimeError("Demo database has not been initialized as synthetic-v1")


def get_demo_db() -> Generator[Session]:
    with Session(get_demo_engine(), autoflush=False, expire_on_commit=False) as session:
        yield session
