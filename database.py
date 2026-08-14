"""Database engine and session configuration.

The connection string is supplied through ``DATABASE_URL`` so credentials stay
outside the repository.  The fallback is a credential-free local PostgreSQL
URL for development; Docker configuration will provide an explicit URL later.
"""

from collections.abc import Generator
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_DATABASE_URL = "postgresql+psycopg://localhost/ccl_suite"


def get_database_url() -> str:
    """Return the configured database URL without embedding credentials."""

    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


class Base(DeclarativeBase):
    """Base class shared by all database models."""


engine = create_engine(get_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield one database session and always close it after use."""

    with SessionLocal() as session:
        yield session
