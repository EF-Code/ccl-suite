"""Add a media editorial lane, file links, and human content reviews."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0024_media_content_delivery"
down_revision: str | Sequence[str] | None = "0023_task_due_reminders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True).with_variant(
        postgresql.UUID(as_uuid=True), "postgresql"
    )
    with op.batch_alter_table("work_items") as batch_op:
        batch_op.add_column(
            sa.Column("work_type", sa.String(length=16), server_default="task", nullable=False)
        )
        batch_op.add_column(sa.Column("content_platform", sa.String(length=24), nullable=True))
        batch_op.add_column(sa.Column("content_channel", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("content_format", sa.String(length=24), nullable=True))
        batch_op.add_column(sa.Column("content_stage", sa.String(length=24), nullable=True))
        batch_op.add_column(sa.Column("publish_date", sa.Date(), nullable=True))
        batch_op.create_check_constraint(
            "ck_work_items_type",
            "work_type IN ('task', 'content')",
        )
        batch_op.create_check_constraint(
            "ck_work_items_content_platform",
            "content_platform IS NULL OR content_platform IN ('youtube', 'tiktok', 'cross_platform', 'other')",
        )
        batch_op.create_check_constraint(
            "ck_work_items_content_format",
            "content_format IS NULL OR content_format IN ('long_video', 'short_video', 'community_post', 'live', 'other')",
        )
        batch_op.create_check_constraint(
            "ck_work_items_content_stage",
            "content_stage IS NULL OR content_stage IN ('brief', 'scripting', 'editing', 'in_review', 'changes_requested', 'approved', 'scheduled', 'published')",
        )
        batch_op.create_check_constraint(
            "ck_work_items_content_metadata",
            "(work_type = 'task' AND content_platform IS NULL AND content_channel IS NULL AND content_format IS NULL AND content_stage IS NULL AND publish_date IS NULL) OR "
            "(work_type = 'content' AND content_platform IS NOT NULL AND content_channel IS NOT NULL AND length(trim(content_channel)) > 0 AND content_format IS NOT NULL AND content_stage IS NOT NULL)",
        )

    op.create_table(
        "work_item_content_assets",
        sa.Column("work_item_id", uuid_type, nullable=False),
        sa.Column("file_id", uuid_type, nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("added_by_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "role IN ('brief', 'script', 'caption', 'thumbnail', 'reference')",
            name="ck_work_item_content_assets_role",
        ),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("work_item_id", "file_id"),
    )
    op.create_index(
        "ix_work_item_content_assets_file",
        "work_item_content_assets",
        ["file_id"],
    )

    op.create_table(
        "work_item_content_reviews",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("work_item_id", uuid_type, nullable=False),
        sa.Column("requested_by_id", uuid_type, nullable=True),
        sa.Column("reviewer_id", uuid_type, nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("request_note", sa.String(length=2000), server_default="", nullable=False),
        sa.Column("decision_note", sa.String(length=2000), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'changes_requested')",
            name="ck_work_item_content_reviews_status",
        ),
        sa.CheckConstraint(
            "length(request_note) <= 2000 AND (decision_note IS NULL OR length(decision_note) <= 2000)",
            name="ck_work_item_content_reviews_note_lengths",
        ),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_work_item_content_reviews_item_requested",
        "work_item_content_reviews",
        ["work_item_id", "requested_at"],
    )
    op.create_index(
        "uq_work_item_content_reviews_pending",
        "work_item_content_reviews",
        ["work_item_id"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )

    with op.batch_alter_table("user_notifications") as batch_op:
        batch_op.drop_constraint("ck_user_notifications_event_type", type_="check")
        batch_op.create_check_constraint(
            "ck_user_notifications_event_type",
            "event_type IN ('task.assigned', 'task.status_changed', 'task.comment_added', "
            "'task.due_soon', 'task.overdue', 'content.review_requested', 'content.review_decided')",
        )


def downgrade() -> None:
    with op.batch_alter_table("user_notifications") as batch_op:
        batch_op.drop_constraint("ck_user_notifications_event_type", type_="check")
        batch_op.create_check_constraint(
            "ck_user_notifications_event_type",
            "event_type IN ('task.assigned', 'task.status_changed', 'task.comment_added', "
            "'task.due_soon', 'task.overdue')",
        )

    op.drop_index(
        "uq_work_item_content_reviews_pending",
        table_name="work_item_content_reviews",
    )
    op.drop_index(
        "ix_work_item_content_reviews_item_requested",
        table_name="work_item_content_reviews",
    )
    op.drop_table("work_item_content_reviews")
    op.drop_index("ix_work_item_content_assets_file", table_name="work_item_content_assets")
    op.drop_table("work_item_content_assets")

    with op.batch_alter_table("work_items") as batch_op:
        batch_op.drop_constraint("ck_work_items_content_metadata", type_="check")
        batch_op.drop_constraint("ck_work_items_content_stage", type_="check")
        batch_op.drop_constraint("ck_work_items_content_format", type_="check")
        batch_op.drop_constraint("ck_work_items_content_platform", type_="check")
        batch_op.drop_constraint("ck_work_items_type", type_="check")
        batch_op.drop_column("publish_date")
        batch_op.drop_column("content_stage")
        batch_op.drop_column("content_format")
        batch_op.drop_column("content_channel")
        batch_op.drop_column("content_platform")
        batch_op.drop_column("work_type")
