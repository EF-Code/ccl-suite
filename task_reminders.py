"""Create idempotent in-app reminders for assigned work approaching its due date."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import Project, ProjectMembership, User, UserNotification, WorkItem

ACTIVE_WORK_ITEM_STATUSES = ("todo", "in_progress", "blocked")
DUE_SOON_DAYS = 1


def evaluate_task_deadline_reminders(db: Session, *, today: date) -> int:
    """Create one due-soon or overdue inbox event per assignee and due date.

    Calendar dates are evaluated in the worker's configured timezone. Only
    active assignees who still have access to the owning project receive
    reminders. The unique notification key makes repeated and overlapping
    evaluations safe.
    """

    statement = (
        select(WorkItem)
        .join(Project, Project.id == WorkItem.project_id)
        .join(User, User.id == WorkItem.assignee_id)
        .where(
            WorkItem.status.in_(ACTIVE_WORK_ITEM_STATUSES),
            WorkItem.due_date.is_not(None),
            WorkItem.due_date <= today + timedelta(days=DUE_SOON_DAYS),
            User.is_active.is_(True),
            or_(
                Project.owner_id == User.id,
                Project.memberships.any(ProjectMembership.user_id == User.id),
            ),
        )
        .order_by(WorkItem.due_date.asc(), WorkItem.id.asc())
    )

    try:
        work_items = list(db.scalars(statement).all())
        notification_values: list[dict[str, object]] = []
        for item in work_items:
            if item.assignee_id is None or item.due_date is None:
                continue

            overdue = item.due_date < today
            event_type = "task.overdue" if overdue else "task.due_soon"
            due_date_text = item.due_date.isoformat()
            notification_values.append(
                {
                    "recipient_id": item.assignee_id,
                    "actor_id": None,
                    "project_id": item.project_id,
                    "work_item_id": item.id,
                    "event_type": event_type,
                    "dedupe_key": (
                        f"task-deadline:v1:{event_type}:{item.id}:"
                        f"{item.assignee_id}:{due_date_text}"
                    ),
                    "title": "Task overdue" if overdue else "Task due soon",
                    "message": (
                        f'"{item.title}" was due {due_date_text}.'
                        if overdue
                        else f'"{item.title}" is due {due_date_text}.'
                    ),
                }
            )

        if not notification_values:
            return 0

        dialect_name = db.get_bind().dialect.name
        insert = {
            "postgresql": postgres_insert,
            "sqlite": sqlite_insert,
        }.get(dialect_name)
        if insert is None:
            raise RuntimeError("Task reminders require PostgreSQL or SQLite.")

        result = db.execute(
            insert(UserNotification)
            .values(notification_values)
            .on_conflict_do_nothing(index_elements=[UserNotification.dedupe_key])
        )
        db.commit()
        return result.rowcount or 0
    except SQLAlchemyError:
        db.rollback()
        raise
