"""Persist deduplicated operational alerts and escalation state."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016_operational_alerts"
down_revision: str | Sequence[str] | None = "0015_security_event_time_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True).with_variant(
        postgresql.UUID(as_uuid=True), "postgresql"
    )
    op.create_table(
        "operational_alerts",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("project_id", uuid_type, nullable=True),
        sa.Column("actor_id", uuid_type, nullable=True),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_ref", sa.String(length=128), nullable=True),
        sa.Column("observed_count", sa.Integer(), nullable=False),
        sa.Column("escalation_level", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by_id", uuid_type, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rule_code IN ('security.high_risk_handoff', 'security.repeated_failures', "
            "'workflow.overdue_approval')",
            name="ck_operational_alerts_rule_code",
        ),
        sa.CheckConstraint(
            "severity IN ('warning', 'high', 'critical')",
            name="ck_operational_alerts_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')",
            name="ck_operational_alerts_status",
        ),
        sa.CheckConstraint(
            "escalation_level BETWEEN 0 AND 2",
            name="ck_operational_alerts_escalation",
        ),
        sa.CheckConstraint(
            "observed_count > 0",
            name="ck_operational_alerts_observed_count",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["acknowledged_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_operational_alerts_fingerprint"),
    )
    op.create_index(
        "ix_operational_alerts_status_severity",
        "operational_alerts",
        ["status", "severity"],
    )
    op.create_index(
        "ix_operational_alerts_project_status",
        "operational_alerts",
        ["project_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operational_alerts_project_status", table_name="operational_alerts"
    )
    op.drop_index(
        "ix_operational_alerts_status_severity", table_name="operational_alerts"
    )
    op.drop_table("operational_alerts")
