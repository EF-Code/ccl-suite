from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api_schemas import UserNotificationResponse
from database import Base
from models import Project, ProjectMembership, User, UserNotification, WorkItem
from task_reminder_worker import configured_interval_seconds, configured_timezone
from task_reminders import evaluate_task_deadline_reminders


@pytest.fixture
def reminder_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def add_task(
    session: Session,
    *,
    due_date: date | None,
    status: str = "todo",
    active_assignee: bool = True,
    project_member: bool = True,
    assigned: bool = True,
) -> WorkItem:
    suffix = uuid4().hex
    owner = User(
        external_ref=f"reminder-owner-{suffix}",
        email=f"owner-{suffix}@example.test",
        is_active=True,
        role="administrator",
    )
    assignee = User(
        external_ref=f"reminder-assignee-{suffix}",
        email=f"assignee-{suffix}@example.test",
        is_active=active_assignee,
        role="staff",
    )
    session.add_all((owner, assignee))
    session.flush()

    project = Project(
        owner_id=owner.id,
        name=f"Reminder project {suffix[:8]}",
        storage_slug=f"reminder-{suffix[:32]}",
    )
    session.add(project)
    session.flush()
    if project_member:
        session.add(
            ProjectMembership(
                project_id=project.id,
                user_id=assignee.id,
                role="member",
                added_by_id=owner.id,
            )
        )

    item = WorkItem(
        project_id=project.id,
        assignee_id=assignee.id if assigned else None,
        title=f"Prepare campaign {suffix[:8]}",
        description="Synthetic reminder test item.",
        status=status,
        priority="normal",
        due_date=due_date,
        created_by_id=owner.id,
    )
    session.add(item)
    session.flush()
    return item


def notification_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(UserNotification)) or 0


def test_deadline_reminders_cover_due_soon_and_overdue_once(reminder_session: Session) -> None:
    today = date(2026, 10, 7)
    add_task(reminder_session, due_date=today)
    add_task(reminder_session, due_date=today + timedelta(days=1))
    add_task(reminder_session, due_date=today - timedelta(days=1))
    add_task(reminder_session, due_date=today + timedelta(days=2))
    add_task(reminder_session, due_date=today, status="done")
    add_task(reminder_session, due_date=today - timedelta(days=1), status="cancelled")
    add_task(reminder_session, due_date=today, active_assignee=False)
    add_task(reminder_session, due_date=today, project_member=False)
    add_task(reminder_session, due_date=today, assigned=False)

    created = evaluate_task_deadline_reminders(reminder_session, today=today)
    notifications = list(
        reminder_session.scalars(
            select(UserNotification).order_by(UserNotification.event_type)
        ).all()
    )

    assert created == 3
    assert [item.event_type for item in notifications] == [
        "task.due_soon",
        "task.due_soon",
        "task.overdue",
    ]
    assert all(item.actor_id is None for item in notifications)
    assert all(item.work_item_id is not None for item in notifications)
    assert all(item.dedupe_key for item in notifications)
    response = UserNotificationResponse.from_model(notifications[0], "Reminder project")
    assert response.event_type == "task.due_soon"
    assert "dedupe_key" not in response.model_dump()

    assert evaluate_task_deadline_reminders(reminder_session, today=today) == 0
    assert notification_count(reminder_session) == 3


def test_changed_deadline_gets_a_new_reminder_and_completed_work_stops(
    reminder_session: Session,
) -> None:
    today = date(2026, 10, 7)
    item = add_task(reminder_session, due_date=today + timedelta(days=1))

    assert evaluate_task_deadline_reminders(reminder_session, today=today) == 1

    item.due_date = today + timedelta(days=3)
    reminder_session.commit()
    assert evaluate_task_deadline_reminders(reminder_session, today=today) == 0

    item.due_date = today
    reminder_session.commit()
    assert evaluate_task_deadline_reminders(reminder_session, today=today) == 1

    item.status = "done"
    item.due_date = today - timedelta(days=1)
    reminder_session.commit()
    assert evaluate_task_deadline_reminders(reminder_session, today=today) == 0
    assert notification_count(reminder_session) == 2


def test_reminder_worker_interval_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CCL_TASK_REMINDER_INTERVAL_SECONDS", raising=False)
    assert configured_interval_seconds() == 900

    monkeypatch.setenv("CCL_TASK_REMINDER_INTERVAL_SECONDS", "60")
    assert configured_interval_seconds() == 60

    for invalid in ("bad", "29", "86401"):
        monkeypatch.setenv("CCL_TASK_REMINDER_INTERVAL_SECONDS", invalid)
        with pytest.raises(ValueError):
            configured_interval_seconds()


def test_reminder_worker_uses_configured_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CCL_TASK_REMINDER_TIMEZONE", "Africa/Lagos")
    assert configured_timezone().key == "Africa/Lagos"

    monkeypatch.setenv("CCL_TASK_REMINDER_TIMEZONE", "Not/A_Timezone")
    with pytest.raises(ValueError, match="valid IANA timezone"):
        configured_timezone()
