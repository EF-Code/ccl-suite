"""Add bounded specialist-agent handoff traces."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0012_multi_agent_security"
down_revision: str | Sequence[str] | None = "0011_workflow_orchestration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_handoffs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("source_agent", sa.String(length=32), nullable=False),
        sa.Column("target_agent", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("input_summary", sa.String(length=255), nullable=False),
        sa.Column("output_summary", sa.String(length=500), nullable=False),
        sa.Column("blocked_reason", sa.String(length=128), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('completed', 'blocked', 'failed')",
            name="ck_agent_handoffs_status",
        ),
        sa.CheckConstraint(
            "length(trim(source_agent)) > 0",
            name="ck_agent_handoffs_source_agent_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(target_agent)) > 0",
            name="ck_agent_handoffs_target_agent_not_blank",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trace_id"),
    )
    op.create_index(
        "ix_agent_handoffs_project_created_at",
        "agent_handoffs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_agent_handoffs_workflow_created_at",
        "agent_handoffs",
        ["workflow_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_handoffs_workflow_created_at", table_name="agent_handoffs")
    op.drop_index("ix_agent_handoffs_project_created_at", table_name="agent_handoffs")
    op.drop_table("agent_handoffs")
