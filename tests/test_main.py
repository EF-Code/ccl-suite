import asyncio
from collections.abc import AsyncIterator, Generator
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import MAX_REQUEST_BODY_BYTES, app
from models import User


TEST_ENGINE = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=TEST_ENGINE,
    autoflush=False,
    expire_on_commit=False,
)
TEST_OWNER_ID = ""


async def override_get_db() -> AsyncIterator[Session]:
    with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def isolated_database() -> Generator[None, None, None]:
    global TEST_OWNER_ID

    Base.metadata.drop_all(TEST_ENGINE)
    Base.metadata.create_all(TEST_ENGINE)

    with TestingSessionLocal() as session:
        owner = User(external_ref="test-owner")
        session.add(owner)
        session.commit()
        TEST_OWNER_ID = str(owner.id)

    yield

    Base.metadata.drop_all(TEST_ENGINE)


def request(method: str, path: str, **kwargs: object) -> httpx.Response:
    """Send one request directly to the ASGI application."""

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_health_reports_ok() -> None:
    response = request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_then_list_projects() -> None:
    created = request(
        "POST",
        "/projects",
        json={
            "title": "First CCL Project",
            "description": "API test",
            "owner_id": TEST_OWNER_ID,
        },
    )
    listed = request("GET", "/projects")

    assert created.status_code == 201
    assert created.json()["title"] == "First CCL Project"
    assert created.json()["owner_id"] == TEST_OWNER_ID
    assert created.json()["status"] == "active"
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_rejects_unknown_project_owner() -> None:
    response = request(
        "POST",
        "/projects",
        json={
            "title": "Unowned",
            "owner_id": str(uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project owner was not found."}


def test_requires_project_owner() -> None:
    response = request("POST", "/projects", json={"title": "Owner required"})

    assert response.status_code == 422


def test_rejects_malformed_project_data() -> None:
    response = request("POST", "/projects", content=b'{"title":')

    assert response.status_code == 422


def test_rejects_unknown_project_fields() -> None:
    response = request(
        "POST",
        "/projects",
        json={
            "title": "Valid",
            "owner_id": TEST_OWNER_ID,
            "owner": "unknown",
        },
    )

    assert response.status_code == 422


def test_rejects_oversized_request_body() -> None:
    response = request("POST", "/projects", content=b"x" * (MAX_REQUEST_BODY_BYTES + 1))

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large."}
