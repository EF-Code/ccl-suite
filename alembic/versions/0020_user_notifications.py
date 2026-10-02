"""Add a durable per-user notification inbox."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0020_user_notifications"
down_revision: str | Sequence[str] | None = "0019_work_item_comments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True).with_variant(
        postgresql.UUID(as_uuid=True), "postgresql"
    )
    op.create_table(
        "user_notifications",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("recipient_id", uuid_type, nullable=False),
        sa.Column("actor_id", uuid_type, nullable=True),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("work_item_id", uuid_type, nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "event_type IN ('task.assigned', 'task.status_changed', 'task.comment_added')",
            name="ck_user_notifications_event_type",
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_user_notifications_title_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(message)) > 0",
            name="ck_user_notifications_message_not_blank",
        ),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_notifications_recipient_read_created",
        "user_notifications",
        ["recipient_id", "read_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_notifications_recipient_read_created",
        table_name="user_notifications",
    )
    op.drop_table("user_notifications")
