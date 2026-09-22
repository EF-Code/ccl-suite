"""Add project intake, workflow states, tool traces, and action gates."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0011_workflow_orchestration"
down_revision: str | Sequence[str] | None = "0010_research_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("category", sa.String(length=80), nullable=False, server_default="general"),
    )
    op.add_column(
        "projects",
        sa.Column("scope", sa.String(length=1000), nullable=False, server_default=""),
    )
    op.add_column("projects", sa.Column("deadline", sa.Date(), nullable=True))
    op.add_column(
        "projects",
        sa.Column(
            "outputs",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "projects",
        sa.Column("responsible_person", sa.String(length=120), nullable=False, server_default=""),
    )

    op.add_column(
        "workflows",
        sa.Column("state", sa.String(length=24), nullable=False, server_default="ready"),
    )
    with op.batch_alter_table("workflows") as batch_op:
        batch_op.create_check_constraint(
            "ck_workflows_state",
            "state IN ('ready', 'in_progress', 'review', 'changes_required', 'approved', 'archived')",
        )

    op.create_table(
        "workflow_actions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("executed_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("action_code", sa.String(length=16), nullable=False),
        sa.Column("target_ref", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("result_summary", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "action_code IN ('send', 'delete', 'replace', 'publish', 'archive', 'approve')",
            name="ck_workflow_actions_code",
        ),
        sa.CheckConstraint(
            "status IN ('pending_approval', 'approved', 'rejected', 'cancelled', 'executed')",
            name="ck_workflow_actions_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["executed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id",
            "idempotency_key",
            name="uq_workflow_actions_workflow_idempotency",
        ),
    )
    op.create_index(
        "ix_workflow_actions_project_status",
        "workflow_actions",
        ["project_id", "status"],
    )

    op.create_table(
        "workflow_tool_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("input_summary", sa.String(length=500), nullable=False),
        sa.Column("output_summary", sa.String(length=1000), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed', 'blocked')",
            name="ck_workflow_tool_runs_status",
        ),
        sa.CheckConstraint(
            "attempt_count > 0",
            name="ck_workflow_tool_runs_attempt_positive",
        ),
        sa.CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 3",
            name="ck_workflow_tool_runs_max_attempts",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trace_id"),
    )
    op.create_index(
        "ix_workflow_tool_runs_project_created_at",
        "workflow_tool_runs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_workflow_tool_runs_workflow_created_at",
        "workflow_tool_runs",
        ["workflow_id", "created_at"],
    )

    op.add_column(
        "approvals",
        sa.Column("action_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    with op.batch_alter_table("approvals") as batch_op:
        batch_op.create_foreign_key(
            "fk_approvals_action_id",
            "workflow_actions",
            ["action_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_approvals_action_id", "approvals", ["action_id"])


def downgrade() -> None:
    op.drop_index("ix_approvals_action_id", table_name="approvals")
    with op.batch_alter_table("approvals") as batch_op:
        batch_op.drop_constraint("fk_approvals_action_id", type_="foreignkey")
        batch_op.drop_column("action_id")

    op.drop_index("ix_workflow_tool_runs_workflow_created_at", table_name="workflow_tool_runs")
    op.drop_index("ix_workflow_tool_runs_project_created_at", table_name="workflow_tool_runs")
    op.drop_table("workflow_tool_runs")
    op.drop_index("ix_workflow_actions_project_status", table_name="workflow_actions")
    op.drop_table("workflow_actions")

    with op.batch_alter_table("workflows") as batch_op:
        batch_op.drop_constraint("ck_workflows_state", type_="check")
        batch_op.drop_column("state")
    op.drop_column("projects", "responsible_person")
    op.drop_column("projects", "outputs")
    op.drop_column("projects", "deadline")
    op.drop_column("projects", "scope")
    op.drop_column("projects", "category")
