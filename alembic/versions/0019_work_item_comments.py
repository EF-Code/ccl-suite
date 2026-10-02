"""Add persistent, project-scoped work-item discussions."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019_work_item_comments"
down_revision: str | Sequence[str] | None = "0018_project_team"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True).with_variant(
        postgresql.UUID(as_uuid=True), "postgresql"
    )
    op.create_table(
        "work_item_comments",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("work_item_id", uuid_type, nullable=False),
        sa.Column("author_id", uuid_type, nullable=True),
        sa.Column("author_label", sa.String(length=254), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "length(trim(body)) > 0",
            name="ck_work_item_comments_body_not_blank",
        ),
        sa.CheckConstraint(
            "length(body) <= 4000",
            name="ck_work_item_comments_body_max_length",
        ),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_work_item_comments_item_created_at",
        "work_item_comments",
        ["work_item_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_work_item_comments_item_created_at", table_name="work_item_comments")
    op.drop_table("work_item_comments")
