import asyncio
import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from database import get_db
from main import app
from models import Project, User


pytestmark = pytest.mark.integration
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    pytest.skip(
        "Set TEST_DATABASE_URL to run the PostgreSQL integration test.",
        allow_module_level=True,
    )


@pytest.fixture(scope="module")
def postgres_engine():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        engine.dispose()
        pytest.fail("TEST_DATABASE_URL is not reachable: database connection failed")

    yield engine
    engine.dispose()


def test_project_endpoint_round_trip_against_postgresql(postgres_engine) -> None:
    session_factory = sessionmaker(
        bind=postgres_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with session_factory() as session:
        owner = User(external_ref=f"integration-{uuid4().hex}")
        session.add(owner)
        session.commit()
        owner_id = str(owner.id)

    async def override_get_db() -> AsyncIterator[Session]:
        with session_factory() as session:
            yield session

    async def send_requests() -> tuple[httpx.Response, httpx.Response]:
        app.dependency_overrides[get_db] = override_get_db
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://integration"
            ) as client:
                created = await client.post(
                    "/projects",
                    json={"title": "PostgreSQL project", "owner_id": owner_id},
                )
                listed = await client.get("/projects")
                return created, listed
        finally:
            app.dependency_overrides.pop(get_db, None)

    created, listed = asyncio.run(send_requests())
    assert created.status_code == 201
    assert listed.status_code == 200
    project_id = UUID(created.json()["id"])

    with session_factory() as session:
        stored_project = session.get(Project, project_id)
        assert stored_project is not None
        assert stored_project.owner_id == UUID(owner_id)

        session.execute(delete(Project).where(Project.id == project_id))
        session.execute(delete(User).where(User.id == UUID(owner_id)))
        session.commit()
