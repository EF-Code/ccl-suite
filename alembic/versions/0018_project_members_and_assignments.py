"""Add explicit project membership and account-backed task assignment."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018_project_team"
down_revision: str | Sequence[str] | None = "0017_project_work_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True).with_variant(
        postgresql.UUID(as_uuid=True), "postgresql"
    )
    op.create_table(
        "project_memberships",
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("role", sa.String(length=16), server_default="member", nullable=False),
        sa.Column("added_by_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "role IN ('manager', 'member')",
            name="ck_project_memberships_role",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("project_id", "user_id"),
    )
    op.create_index(
        "ix_project_memberships_user_project",
        "project_memberships",
        ["user_id", "project_id"],
    )
    op.execute(
        sa.text(
            "INSERT INTO project_memberships "
            "(project_id, user_id, role, added_by_id, created_at) "
            "SELECT id, owner_id, 'manager', NULL, CURRENT_TIMESTAMP FROM projects"
        )
    )

    with op.batch_alter_table("work_items") as batch_op:
        batch_op.add_column(sa.Column("assignee_id", uuid_type, nullable=True))
        batch_op.create_foreign_key(
            "fk_work_items_assignee_id_users",
            "users",
            ["assignee_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_work_items_assignee_status_due",
            ["assignee_id", "status", "due_date"],
        )


def downgrade() -> None:
    with op.batch_alter_table("work_items") as batch_op:
        batch_op.drop_index("ix_work_items_assignee_status_due")
        batch_op.drop_constraint("fk_work_items_assignee_id_users", type_="foreignkey")
        batch_op.drop_column("assignee_id")
    op.drop_index("ix_project_memberships_user_project", table_name="project_memberships")
    op.drop_table("project_memberships")
