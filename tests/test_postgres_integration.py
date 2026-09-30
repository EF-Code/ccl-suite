import asyncio
import os
import threading
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

import main
from auth import hash_password, token_digest, verify_password
from database import get_db
from main import app
from models import AuthSession, Project, SecurityEvent, User
from scripts import reset_account_password as password_recovery


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


def test_password_reset_serializes_with_concurrent_login(postgres_engine, monkeypatch) -> None:
    session_factory = sessionmaker(
        bind=postgres_engine,
        autoflush=False,
        expire_on_commit=False,
    )
    email = f"reset-race-{uuid4().hex}@example.test"
    old_password = "Postgres-Reset-Race-Password-26!"
    replacement_password = "Postgres-Reset-Replacement-26!"
    second_replacement = "Postgres-Reset-Second-Password-26!"
    with session_factory() as session:
        user = User(
            external_ref=f"reset-race-{uuid4().hex}",
            email=email,
            password_hash=hash_password(old_password),
            is_active=True,
            role="administrator",
        )
        session.add(user)
        session.commit()
        user_id = user.id

    async def override_get_db() -> AsyncIterator[Session]:
        with session_factory() as session:
            yield session

    async def send_login(password: str) -> tuple[int, str | None]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://integration"
        ) as client:
            response = await client.post(
                "/auth/login", json={"email": email, "password": password}
            )
            return response.status_code, response.cookies.get("ccl_session")

    def login(password: str) -> tuple[int, str | None]:
        return asyncio.run(send_login(password))

    def reset(password: str) -> None:
        with session_factory() as session:
            password_recovery.reset_account_password(session, email, password)

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    original_verify = main.verify_password
    original_hash = password_recovery.hash_password
    try:
        # Login locks and reads the account first. Recovery must wait, then see
        # and revoke the session created by that in-flight login.
        password_checked = threading.Event()
        release_login = threading.Event()

        def pause_login(candidate: str, stored_hash: str | None) -> bool:
            password_checked.set()
            if not release_login.wait(timeout=10):
                raise TimeoutError("test did not release the paused login")
            return verify_password(candidate, stored_hash)

        monkeypatch.setattr(main, "verify_password", pause_login)
        with ThreadPoolExecutor(max_workers=2) as workers:
            login_future = workers.submit(login, old_password)
            assert password_checked.wait(timeout=10)
            reset_future = workers.submit(reset, replacement_password)
            release_login.set()
            login_status, session_token = login_future.result(timeout=15)
            reset_future.result(timeout=15)

        assert login_status == 200
        assert session_token
        with session_factory() as session:
            issued_session = session.get(AuthSession, token_digest(session_token))
            assert issued_session is not None
            assert issued_session.revoked_at is not None

        # Recovery locks and updates first. A login queued behind it must read
        # the new hash and reject the previous password.
        hash_started = threading.Event()
        release_hash = threading.Event()
        def pause_hash(password: str) -> str:
            hash_started.set()
            if not release_hash.wait(timeout=10):
                raise TimeoutError("test did not release the paused password reset")
            return original_hash(password)

        monkeypatch.setattr(password_recovery, "hash_password", pause_hash)
        with ThreadPoolExecutor(max_workers=2) as workers:
            reset_future = workers.submit(reset, second_replacement)
            assert hash_started.wait(timeout=10)
            login_future = workers.submit(login, replacement_password)
            release_hash.set()
            reset_future.result(timeout=15)
            login_status, session_token = login_future.result(timeout=15)

        assert login_status == 401
        assert session_token is None
    finally:
        monkeypatch.setattr(main, "verify_password", original_verify)
        monkeypatch.setattr(password_recovery, "hash_password", original_hash)
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        with session_factory() as session:
            session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
            session.execute(
                delete(SecurityEvent).where(
                    SecurityEvent.resource_ref == str(user_id),
                    SecurityEvent.event_code == "auth.password.reset",
                )
            )
            session.execute(delete(User).where(User.id == user_id))
            session.commit()
