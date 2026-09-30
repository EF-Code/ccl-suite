"""Database engine and session configuration.

An explicit ``DATABASE_URL`` takes precedence. Docker can provide credentials
as separate ``CCL_DATABASE_*`` components, which are safely URL-encoded here.
"""

import os
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_DATABASE_URL = "postgresql+psycopg://localhost/ccl_suite"


def get_database_url() -> str:
    """Return a database URL, safely escaping component-based credentials."""

    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        return configured_url

    database_host = os.getenv("CCL_DATABASE_HOST")
    if database_host:
        password_file = os.getenv("CCL_DATABASE_PASSWORD_FILE")
        if password_file:
            database_password = Path(password_file).read_text(encoding="utf-8").rstrip("\r\n")
            if not database_password:
                raise ValueError("CCL_DATABASE_PASSWORD_FILE must contain a password.")
        else:
            database_password = os.getenv("CCL_DATABASE_PASSWORD")
        database_url = URL.create(
            "postgresql+psycopg",
            username=os.getenv("CCL_DATABASE_USER", "ccl_suite"),
            password=database_password,
            host=database_host,
            port=int(os.getenv("CCL_DATABASE_PORT", "5432")),
            database=os.getenv("CCL_DATABASE_NAME", "ccl_suite"),
        )
        return database_url.render_as_string(hide_password=False)

    return DEFAULT_DATABASE_URL


class Base(DeclarativeBase):
    """Base class shared by all database models."""


engine = create_engine(get_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


async def get_db() -> AsyncIterator[Session]:
    """Yield one database session and always close it after use."""

    with SessionLocal() as session:
        yield session
