import asyncio
import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from auth import hash_password
from database import get_db
from main import app
from models import AuthSession, Project, User


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

    email = f"integration-{uuid4().hex}@example.test"
    password = "Postgres-Integration-Password-26!"
    with session_factory() as session:
        owner = User(
            external_ref=f"integration-{uuid4().hex}",
            email=email,
            password_hash=hash_password(password),
            is_active=True,
            role="administrator",
        )
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
                login = await client.post(
                    "/auth/login",
                    json={"email": email, "password": password},
                )
                assert login.status_code == 200, login.text
                csrf_token = client.cookies.get("ccl_csrf")
                assert csrf_token
                created = await client.post(
                    "/projects",
                    json={"title": "PostgreSQL project", "owner_id": owner_id},
                    headers={"X-CSRF-Token": csrf_token},
                )
                listed = await client.get("/projects")
                return created, listed
        finally:
            app.dependency_overrides.pop(get_db, None)

    project_id: UUID | None = None
    try:
        created, listed = asyncio.run(send_requests())
        if created.status_code == 201:
            project_id = UUID(created.json()["id"])
        assert created.status_code == 201, created.text
        assert listed.status_code == 200

        with session_factory() as session:
            stored_project = session.get(Project, project_id)
            assert stored_project is not None
            assert stored_project.owner_id == UUID(owner_id)
    finally:
        with session_factory() as session:
            if project_id is not None:
                session.execute(delete(Project).where(Project.id == project_id))
            session.execute(delete(AuthSession).where(AuthSession.user_id == UUID(owner_id)))
            session.execute(delete(User).where(User.id == UUID(owner_id)))
            session.commit()
