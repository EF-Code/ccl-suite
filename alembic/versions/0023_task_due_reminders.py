"""Add idempotency keys and deadline events to the task notification inbox."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023_task_due_reminders"
down_revision: str | Sequence[str] | None = "0022_password_reset_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_notifications") as batch_op:
        batch_op.add_column(sa.Column("dedupe_key", sa.String(length=255), nullable=True))
        batch_op.drop_constraint("ck_user_notifications_event_type", type_="check")
        batch_op.create_check_constraint(
            "ck_user_notifications_event_type",
            "event_type IN ('task.assigned', 'task.status_changed', "
            "'task.comment_added', 'task.due_soon', 'task.overdue')",
        )
    op.create_index(
        "uq_user_notifications_dedupe_key",
        "user_notifications",
        ["dedupe_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_user_notifications_dedupe_key", table_name="user_notifications")
    with op.batch_alter_table("user_notifications") as batch_op:
        batch_op.drop_constraint("ck_user_notifications_event_type", type_="check")
        batch_op.create_check_constraint(
            "ck_user_notifications_event_type",
            "event_type IN ('task.assigned', 'task.status_changed', 'task.comment_added')",
        )
        batch_op.drop_column("dedupe_key")
