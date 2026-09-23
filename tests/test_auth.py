"""End-to-end invite, session, CSRF, and legacy-header boundary tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from auth import hash_password, token_digest
from database import Base, get_db
from main import app
from models import AuthSession, Invitation, User, utc_now


@pytest.fixture
def auth_database(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with sessions() as db:
        admin = User(
            external_ref=f"admin:{uuid4().hex}",
            email="admin@example.test",
            password_hash=hash_password("correct horse battery staple"),
            is_active=True,
            role="administrator",
        )
        db.add(admin)
        db.commit()
        admin_id = admin.id

    async def override() -> AsyncIterator[Session]:
        with sessions() as db:
            yield db

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override
    monkeypatch.setattr("main.ENVIRONMENT", "development")
    yield sessions, admin_id
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    engine.dispose()


def test_login_ignores_asserted_user_id_and_requires_csrf(auth_database) -> None:
    sessions, admin_id = auth_database

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.get("/projects", headers={"X-User-ID": str(admin_id)})).status_code == 401
            assert (await client.post("/users", json={"external_ref": "attack"})).status_code == 403
            wrong = await client.post(
                "/auth/login", json={"email": "admin@example.test", "password": "wrong"}
            )
            assert wrong.status_code == 401
            login = await client.post(
                "/auth/login",
                json={"email": "ADMIN@example.test", "password": "correct horse battery staple"},
            )
            assert login.status_code == 200
            assert login.json() == {"id": str(admin_id), "email": "admin@example.test", "role": "administrator"}
            assert "httponly" in login.headers["set-cookie"].lower()
            csrf = client.cookies["ccl_csrf"]
            assert (await client.get("/auth/me")).status_code == 200
            payload = {"title": "Authenticated Project", "owner_id": str(admin_id)}
            assert (await client.post("/projects", json=payload)).status_code == 403
            created = await client.post(
                "/projects", json=payload, headers={"X-CSRF-Token": csrf}
            )
            assert created.status_code == 201
            assert (await client.post("/auth/logout", headers={"X-CSRF-Token": csrf})).status_code == 204
            assert (await client.get("/auth/me")).status_code == 401

    asyncio.run(scenario())
    with sessions() as db:
        session = db.scalar(select(AuthSession))
        assert session is not None and session.revoked_at is not None
        assert len(session.token_hash) == 64


def test_invitation_is_single_use_and_account_can_be_disabled(auth_database) -> None:
    sessions, _admin_id = auth_database

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as admin:
            await admin.post(
                "/auth/login",
                json={"email": "admin@example.test", "password": "correct horse battery staple"},
            )
            csrf = admin.cookies["ccl_csrf"]
            created = await admin.post(
                "/auth/invitations",
                json={"email": "Teammate@example.test", "role": "staff"},
                headers={"X-CSRF-Token": csrf},
            )
            assert created.status_code == 201
            invitation = created.json()
            token = invitation["invite_url"].split("invite=", 1)[1]
            assert invitation["email"] == "teammate@example.test"
            with sessions() as db:
                record = db.get(Invitation, UUID(invitation["id"]))
                assert record is not None and record.token_hash == token_digest(token)
                assert token not in record.token_hash

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as teammate:
                accepted = await teammate.post(
                    "/auth/invitations/accept",
                    json={"token": token, "password": "new long account password"},
                )
                assert accepted.status_code == 201
                assert accepted.json()["role"] == "staff"
                assert (await teammate.get("/auth/me")).status_code == 200
                assert (await teammate.post(
                    "/auth/invitations",
                    json={"email": "third@example.test", "role": "staff"},
                    headers={"X-CSRF-Token": teammate.cookies["ccl_csrf"]},
                )).status_code == 403
                assert (await teammate.post(
                    "/auth/invitations/accept",
                    json={"token": token, "password": "another long password"},
                )).status_code == 400
                disabled = await admin.post(
                    f"/auth/users/{accepted.json()['id']}/disable",
                    headers={"X-CSRF-Token": csrf},
                )
                assert disabled.status_code == 204
                assert (await teammate.get("/auth/me")).status_code == 401

    asyncio.run(scenario())


def test_revoked_and_expired_invitations_cannot_be_accepted(auth_database) -> None:
    sessions, _admin_id = auth_database

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/auth/login",
                json={"email": "admin@example.test", "password": "correct horse battery staple"},
            )
            csrf = client.cookies["ccl_csrf"]
            created = await client.post(
                "/auth/invitations",
                json={"email": "revoked@example.test", "role": "intern"},
                headers={"X-CSRF-Token": csrf},
            )
            token = created.json()["invite_url"].split("invite=", 1)[1]
            assert (await client.post(
                f"/auth/invitations/{created.json()['id']}/revoke",
                headers={"X-CSRF-Token": csrf},
            )).status_code == 204
            assert (await client.post(
                "/auth/invitations/accept",
                json={"token": token, "password": "new long account password"},
            )).status_code == 400

            expired = await client.post(
                "/auth/invitations",
                json={"email": "expired@example.test", "role": "staff"},
                headers={"X-CSRF-Token": csrf},
            )
            with sessions() as db:
                record = db.get(Invitation, UUID(expired.json()["id"]))
                assert record is not None
                record.expires_at = utc_now() - timedelta(seconds=1)
                db.commit()
            expired_token = expired.json()["invite_url"].split("invite=", 1)[1]
            assert (await client.post(
                "/auth/invitations/accept",
                json={"token": expired_token, "password": "new long account password"},
            )).status_code == 400

    asyncio.run(scenario())


def test_login_throttles_repeated_failures(auth_database) -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(5):
                response = await client.post(
                    "/auth/login",
                    json={"email": "admin@example.test", "password": "wrong"},
                )
                assert response.status_code == 401
            blocked = await client.post(
                "/auth/login",
                json={"email": "admin@example.test", "password": "correct horse battery staple"},
            )
            assert blocked.status_code == 429

    asyncio.run(scenario())
