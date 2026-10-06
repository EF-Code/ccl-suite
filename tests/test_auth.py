"""End-to-end invite, session, CSRF, and legacy-header boundary tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from auth import hash_password, token_digest, verify_password
from database import Base, get_db
from main import app
from models import (
    AuthSession,
    Invitation,
    PasswordResetToken,
    Project,
    ProjectMembership,
    SecurityEvent,
    User,
    WorkItem,
    utc_now,
)
from scripts.reset_account_password import reset_account_password


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
    sessions, admin_id = auth_database

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as admin:
            await admin.post(
                "/auth/login",
                json={"email": "admin@example.test", "password": "correct horse battery staple"},
            )
            csrf = admin.cookies["ccl_csrf"]
            self_disable = await admin.post(
                f"/auth/users/{admin_id}/disable",
                headers={"X-CSRF-Token": csrf},
            )
            assert self_disable.status_code == 409
            own_account = await admin.get("/auth/users")
            assert own_account.status_code == 200
            assert own_account.headers["cache-control"] == "no-store"
            assert own_account.json() == [{
                "id": str(admin_id),
                "email": "admin@example.test",
                "role": "administrator",
                "is_active": True,
            }]
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
                assert (await teammate.get("/auth/users")).status_code == 403
                assert (await teammate.get(
                    f"/auth/users/{admin_id}/offboarding-impact"
                )).status_code == 403
                assert (await teammate.post(
                    f"/auth/users/{admin_id}/enable",
                    headers={"X-CSRF-Token": teammate.cookies["ccl_csrf"]},
                )).status_code == 403
                assert (await teammate.post(
                    "/auth/invitations/accept",
                    json={"token": token, "password": "another long password"},
                )).status_code == 400
                teammate_id = accepted.json()["id"]
                active_accounts = await admin.get("/auth/users")
                assert active_accounts.status_code == 200
                assert next(item for item in active_accounts.json() if item["id"] == teammate_id)["is_active"]
                disabled = await admin.post(
                    f"/auth/users/{teammate_id}/disable",
                    headers={"X-CSRF-Token": csrf},
                )
                assert disabled.status_code == 204
                assert (await teammate.get("/auth/me")).status_code == 401
                disabled_accounts = await admin.get("/auth/users")
                disabled_member = next(item for item in disabled_accounts.json() if item["id"] == teammate_id)
                assert disabled_member["is_active"] is False
                assert set(disabled_member) == {"id", "email", "role", "is_active"}

                enabled = await admin.post(
                    f"/auth/users/{teammate_id}/enable",
                    headers={"X-CSRF-Token": csrf},
                )
                assert enabled.status_code == 204
                assert (await teammate.get("/auth/me")).status_code == 401
                relogin = await teammate.post(
                    "/auth/login",
                    json={
                        "email": "teammate@example.test",
                        "password": "new long account password",
                    },
                )
                assert relogin.status_code == 200
                assert (await teammate.get("/auth/me")).status_code == 200

    asyncio.run(scenario())
    with sessions() as db:
        events = db.scalars(
            select(SecurityEvent).where(
                SecurityEvent.event_code.in_(
                    {"user.account.disabled", "user.account.enabled"}
                )
            )
        ).all()
        assert {event.event_code for event in events} == {
            "user.account.disabled",
            "user.account.enabled",
        }
        assert all(event.outcome == "success" for event in events)


def test_account_offboarding_transfers_projects_and_open_work_atomically(auth_database) -> None:
    sessions, admin_id = auth_database
    with sessions() as db:
        target = User(
            external_ref="offboarding-target",
            email="leaving@example.test",
            password_hash=hash_password("a sufficiently long password"),
            is_active=True,
            role="staff",
        )
        replacement = User(
            external_ref="offboarding-replacement",
            email="replacement@example.test",
            is_active=True,
            role="supervisor",
        )
        intern = User(
            external_ref="offboarding-intern",
            email="intern@example.test",
            is_active=True,
            role="intern",
        )
        db.add_all([target, replacement, intern])
        db.flush()
        owned_project = Project(
            owner_id=target.id,
            name="Owned project",
            storage_slug="offboarding-owned-project",
        )
        task_project = Project(
            owner_id=admin_id,
            name="Assigned project",
            storage_slug="offboarding-assigned-project",
        )
        db.add_all([owned_project, task_project])
        db.flush()
        open_owned_item = WorkItem(
            project_id=owned_project.id,
            assignee_id=target.id,
            title="Open owned task",
            status="in_progress",
        )
        open_other_item = WorkItem(
            project_id=task_project.id,
            assignee_id=target.id,
            title="Open assigned task",
            status="todo",
        )
        completed_item = WorkItem(
            project_id=task_project.id,
            assignee_id=target.id,
            title="Completed historical task",
            status="done",
        )
        legacy_email_item = WorkItem(
            project_id=task_project.id,
            assignee=" LEAVING@example.test ",
            title="Legacy email-assigned task",
            status="todo",
        )
        unrelated_legacy_item = WorkItem(
            project_id=task_project.id,
            assignee="Unlinked colleague",
            title="Unlinked legacy task",
            status="todo",
        )
        db.add_all(
            [
                ProjectMembership(
                    project_id=owned_project.id,
                    user_id=target.id,
                    role="manager",
                    added_by_id=admin_id,
                ),
                ProjectMembership(
                    project_id=task_project.id,
                    user_id=target.id,
                    role="member",
                    added_by_id=admin_id,
                ),
                ProjectMembership(
                    project_id=owned_project.id,
                    user_id=replacement.id,
                    role="member",
                    added_by_id=admin_id,
                ),
                open_owned_item,
                open_other_item,
                completed_item,
                legacy_email_item,
                unrelated_legacy_item,
                AuthSession(
                    token_hash="a" * 64,
                    csrf_hash="b" * 64,
                    user_id=target.id,
                    expires_at=utc_now() + timedelta(hours=1),
                ),
                PasswordResetToken(
                    user_id=target.id,
                    token_hash="d" * 64,
                    expires_at=utc_now() + timedelta(minutes=15),
                ),
            ]
        )
        db.commit()
        target_id = target.id
        replacement_id = replacement.id
        intern_id = intern.id
        owned_project_id = owned_project.id
        task_project_id = task_project.id
        open_owned_item_id = open_owned_item.id
        open_other_item_id = open_other_item.id
        completed_item_id = completed_item.id
        legacy_email_item_id = legacy_email_item.id
        unrelated_legacy_item_id = unrelated_legacy_item.id

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as admin:
            await admin.post(
                "/auth/login",
                json={"email": "admin@example.test", "password": "correct horse battery staple"},
            )
            csrf = admin.cookies["ccl_csrf"]
            headers = {"X-CSRF-Token": csrf}
            impact = await admin.get(f"/auth/users/{target_id}/offboarding-impact")
            assert impact.status_code == 200
            assert impact.headers["cache-control"] == "no-store"
            report = impact.json()
            assert report["open_work_items_total"] == 3
            assert report["memberships_to_remove"] == 2
            owned_impact = next(project for project in report["projects"] if project["project_id"] == str(owned_project_id))
            assert owned_impact["ownership_transfers"] is True
            assert owned_impact["open_work_items_to_reassign"] == 1
            task_impact = next(project for project in report["projects"] if project["project_id"] == str(task_project_id))
            assert task_impact["open_work_items_to_reassign"] == 2
            assert task_impact["legacy_email_assignments"] == 1
            assert all(item["id"] != str(intern_id) for item in report["eligible_replacements"])

            missing_replacement = await admin.post(
                f"/auth/users/{target_id}/disable", headers=headers
            )
            assert missing_replacement.status_code == 409
            with sessions() as db:
                assert db.get(User, target_id).is_active is True
                assert db.get(Project, owned_project_id).owner_id == target_id
                assert db.get(WorkItem, open_owned_item_id).assignee_id == target_id

            intern_replacement = await admin.post(
                f"/auth/users/{target_id}/disable",
                headers=headers,
                json={"replacement_user_id": str(intern_id)},
            )
            assert intern_replacement.status_code == 409

            disabled = await admin.post(
                f"/auth/users/{target_id}/disable",
                headers=headers,
                json={"replacement_user_id": str(replacement_id)},
            )
            assert disabled.status_code == 204

    asyncio.run(scenario())
    with sessions() as db:
        assert db.get(User, target_id).is_active is False
        assert db.get(Project, owned_project_id).owner_id == replacement_id
        assert db.get(WorkItem, open_owned_item_id).assignee_id == replacement_id
        assert db.get(WorkItem, open_other_item_id).assignee_id == replacement_id
        assert db.get(WorkItem, completed_item_id).assignee_id == target_id
        assert db.get(WorkItem, legacy_email_item_id).assignee_id == replacement_id
        assert db.get(WorkItem, legacy_email_item_id).assignee is None
        assert db.get(WorkItem, unrelated_legacy_item_id).assignee_id is None
        assert db.get(WorkItem, unrelated_legacy_item_id).assignee == "Unlinked colleague"
        assert db.get(ProjectMembership, (owned_project_id, replacement_id)).role == "manager"
        assert db.get(ProjectMembership, (task_project_id, replacement_id)).role == "member"
        assert db.get(ProjectMembership, (owned_project_id, target_id)) is None
        assert db.get(ProjectMembership, (task_project_id, target_id)) is None
        revoked_session = db.scalar(select(AuthSession).where(AuthSession.user_id == target_id))
        assert revoked_session is not None and revoked_session.revoked_at is not None
        pending_reset = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.user_id == target_id)
        )
        assert pending_reset is not None and pending_reset.used_at is not None
        events = db.scalars(
            select(SecurityEvent).where(
                SecurityEvent.event_code.in_(
                    {
                        "user.account.disabled",
                        "project.ownership.transferred",
                        "work_item.reassigned",
                    }
                )
            )
        ).all()
        assert sum(event.event_code == "project.ownership.transferred" for event in events) == 1
        assert sum(event.event_code == "work_item.reassigned" for event in events) == 3
        assert sum(event.event_code == "user.account.disabled" for event in events) == 1


def test_previously_disabled_account_can_complete_project_handoff(auth_database) -> None:
    sessions, admin_id = auth_database
    with sessions() as db:
        target = User(
            external_ref="legacy-disabled-target",
            email="previously-disabled@example.test",
            is_active=False,
            role="staff",
        )
        replacement = User(
            external_ref="legacy-disabled-replacement",
            email="handoff@example.test",
            is_active=True,
            role="staff",
        )
        db.add_all([target, replacement])
        db.flush()
        project = Project(
            owner_id=target.id,
            name="Legacy project",
            storage_slug="legacy-disabled-owned-project",
        )
        db.add(project)
        db.flush()
        db.add_all(
            [
                ProjectMembership(
                    project_id=project.id,
                    user_id=target.id,
                    role="manager",
                    added_by_id=admin_id,
                ),
                WorkItem(
                    project_id=project.id,
                    assignee_id=target.id,
                    title="Unfinished legacy task",
                    status="blocked",
                ),
            ]
        )
        db.commit()
        target_id = target.id
        replacement_id = replacement.id
        project_id = project.id

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as admin:
            await admin.post(
                "/auth/login",
                json={"email": "admin@example.test", "password": "correct horse battery staple"},
            )
            csrf = admin.cookies["ccl_csrf"]
            impact = await admin.get(f"/auth/users/{target_id}/offboarding-impact")
            assert impact.status_code == 200
            assert impact.json()["is_active"] is False
            assert impact.json()["open_work_items_total"] == 1
            headers = {"X-CSRF-Token": csrf}
            cannot_reassign_project = await admin.post(
                "/projects",
                headers=headers,
                json={"title": "Owned by disabled account", "owner_id": str(target_id)},
            )
            assert cannot_reassign_project.status_code == 404
            blocked = await admin.post(
                f"/auth/users/{target_id}/disable", headers=headers
            )
            assert blocked.status_code == 409
            transferred = await admin.post(
                f"/auth/users/{target_id}/disable",
                headers=headers,
                json={"replacement_user_id": str(replacement_id)},
            )
            assert transferred.status_code == 204

    asyncio.run(scenario())
    with sessions() as db:
        assert db.get(User, target_id).is_active is False
        assert db.get(Project, project_id).owner_id == replacement_id
        assert db.get(ProjectMembership, (project_id, target_id)) is None
        assert db.get(ProjectMembership, (project_id, replacement_id)).role == "manager"
        item = db.scalar(select(WorkItem).where(WorkItem.project_id == project_id))
        assert item is not None and item.assignee_id == replacement_id


def test_account_offboarding_rolls_back_all_changes_when_audit_write_fails(auth_database) -> None:
    sessions, admin_id = auth_database
    with sessions() as db:
        target = User(
            external_ref="rollback-offboarding-target",
            email="rollback-target@example.test",
            is_active=True,
            role="staff",
        )
        replacement = User(
            external_ref="rollback-offboarding-replacement",
            email="rollback-replacement@example.test",
            is_active=True,
            role="staff",
        )
        db.add_all([target, replacement])
        db.flush()
        project = Project(
            owner_id=target.id,
            name="Rollback project",
            storage_slug="rollback-offboarding-project",
        )
        db.add(project)
        db.flush()
        item = WorkItem(
            project_id=project.id,
            assignee_id=target.id,
            title="Must remain assigned",
            status="todo",
        )
        db.add_all(
            [
                ProjectMembership(
                    project_id=project.id,
                    user_id=target.id,
                    role="manager",
                    added_by_id=admin_id,
                ),
                item,
            ]
        )
        db.commit()
        target_id = target.id
        replacement_id = replacement.id
        project_id = project.id
        item_id = item.id
        db.execute(
            text(
                """CREATE TRIGGER reject_work_item_reassignment_audit
                BEFORE INSERT ON security_events
                WHEN NEW.event_code = 'work_item.reassigned'
                BEGIN SELECT RAISE(ABORT, 'simulated audit-store failure'); END"""
            )
        )
        db.commit()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as admin:
            await admin.post(
                "/auth/login",
                json={"email": "admin@example.test", "password": "correct horse battery staple"},
            )
            result = await admin.post(
                f"/auth/users/{target_id}/disable",
                headers={"X-CSRF-Token": admin.cookies["ccl_csrf"]},
                json={"replacement_user_id": str(replacement_id)},
            )
            assert result.status_code == 409
            assert "no changes were saved" in result.json()["detail"]

    asyncio.run(scenario())
    with sessions() as db:
        assert db.get(User, target_id).is_active is True
        assert db.get(Project, project_id).owner_id == target_id
        assert db.get(WorkItem, item_id).assignee_id == target_id
        assert db.get(ProjectMembership, (project_id, target_id)) is not None
        assert db.get(ProjectMembership, (project_id, replacement_id)) is None
        assert db.scalar(
            select(SecurityEvent).where(
                SecurityEvent.event_code == "user.account.disabled",
                SecurityEvent.resource_ref == str(target_id),
            )
        ) is None


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


def test_local_password_recovery_revokes_sessions_and_records_an_audit_event(
    auth_database,
) -> None:
    sessions, admin_id = auth_database
    with sessions() as db:
        db.add(
            AuthSession(
                token_hash="a" * 64,
                csrf_hash="b" * 64,
                user_id=admin_id,
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        db.add(
            PasswordResetToken(
                user_id=admin_id,
                token_hash="c" * 64,
                expires_at=utc_now() + timedelta(minutes=15),
            )
        )
        db.commit()

        user_id, revoked_sessions, audit_reference = reset_account_password(
            db, " ADMIN@example.test ", "replacement administrator password"
        )

    assert user_id == str(admin_id)
    assert revoked_sessions == 1
    with sessions() as db:
        user = db.get(User, admin_id)
        assert user is not None and verify_password("replacement administrator password", user.password_hash)
        assert not verify_password("correct horse battery staple", user.password_hash)
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == admin_id))
        assert session is not None and session.revoked_at is not None
        reset_token = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.user_id == admin_id)
        )
        assert reset_token is not None and reset_token.used_at is not None
        event = db.scalar(
            select(SecurityEvent).where(SecurityEvent.request_ref == audit_reference)
        )
        assert event is not None
        assert event.actor_id is None
        assert event.event_code == "auth.password.reset"
        assert event.resource_ref == str(admin_id)


def test_local_password_recovery_refuses_disabled_accounts(auth_database) -> None:
    sessions, admin_id = auth_database
    with sessions() as db:
        user = db.get(User, admin_id)
        assert user is not None
        user.is_active = False
        db.commit()

        with pytest.raises(ValueError, match="No active password-enabled account"):
            reset_account_password(db, "admin@example.test", "replacement administrator password")

        assert db.scalar(select(SecurityEvent)) is None


def test_password_reset_request_is_generic_and_throttled(auth_database, monkeypatch) -> None:
    sessions, _admin_id = auth_database
    monkeypatch.setenv("CCL_PUBLIC_URL", "http://test")
    deliveries: list[tuple[str, str, object]] = []

    def capture_delivery(recipient: str, reset_url: str, expires_at) -> bool:
        deliveries.append((recipient, reset_url, expires_at))
        return True

    monkeypatch.setattr("main.send_password_reset_email", capture_delivery)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            responses = [
                await client.post(
                    "/auth/password-reset-requests",
                    json={"email": "missing@example.test"},
                ),
                *[
                    await client.post(
                        "/auth/password-reset-requests",
                        json={"email": "admin@example.test"},
                    )
                    for _ in range(4)
                ],
            ]

        assert all(response.status_code == 202 for response in responses)
        assert len({response.json()["message"] for response in responses}) == 1
        assert len(deliveries) == 3
        assert all(delivery[0] == "admin@example.test" for delivery in deliveries)
        assert all("#reset=" in delivery[1] for delivery in deliveries)

    asyncio.run(scenario())
    with sessions() as db:
        records = db.scalars(select(PasswordResetToken)).all()
        assert len(records) == 3
        assert all(len(record.token_hash) == 64 for record in records)
        assert all("admin@example.test" not in record.token_hash for record in records)
        # New requests invalidate earlier links, leaving only the newest usable.
        assert sum(record.used_at is None for record in records) == 1


def test_password_reset_completion_revokes_sessions_and_is_single_use(
    auth_database, monkeypatch
) -> None:
    sessions, admin_id = auth_database
    monkeypatch.setenv("CCL_PUBLIC_URL", "http://test")
    deliveries: list[tuple[str, str, object]] = []

    def capture_delivery(recipient: str, reset_url: str, expires_at) -> bool:
        deliveries.append((recipient, reset_url, expires_at))
        return True

    monkeypatch.setattr("main.send_password_reset_email", capture_delivery)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            login = await client.post(
                "/auth/login",
                json={"email": "admin@example.test", "password": "correct horse battery staple"},
            )
            assert login.status_code == 200
            request = await client.post(
                "/auth/password-reset-requests",
                json={"email": "admin@example.test"},
            )
            assert request.status_code == 202
            token = deliveries[0][1].partition("#reset=")[2]
            assert token

            completed = await client.post(
                "/auth/password-resets/complete",
                json={"token": token, "password": "replacement account password"},
            )
            assert completed.status_code == 204
            assert completed.headers["cache-control"] == "no-store"
            assert (await client.get("/auth/me")).status_code == 401
            reused = await client.post(
                "/auth/password-resets/complete",
                json={"token": token, "password": "another replacement password"},
            )
            assert reused.status_code == 400
            old_login = await client.post(
                "/auth/login",
                json={"email": "admin@example.test", "password": "correct horse battery staple"},
            )
            assert old_login.status_code == 401
            new_login = await client.post(
                "/auth/login",
                json={"email": "admin@example.test", "password": "replacement account password"},
            )
            assert new_login.status_code == 200

    asyncio.run(scenario())
    with sessions() as db:
        record = db.scalar(select(PasswordResetToken))
        assert record is not None and record.used_at is not None
        user = db.get(User, admin_id)
        assert user is not None and verify_password("replacement account password", user.password_hash)
        events = db.scalars(
            select(SecurityEvent).where(SecurityEvent.event_code == "auth.password.reset")
        ).all()
        assert len(events) == 1
        assert events[0].actor_id is None
        assert events[0].resource_ref == str(admin_id)
        assert events[0].request_ref
        assert "admin@example.test" not in (events[0].resource_ref or "")
