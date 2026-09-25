"""Index security events by occurrence time for bounded dashboard queries."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015_security_event_time_index"
down_revision: str | Sequence[str] | None = "0014_invite_authentication"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_security_events_occurred_at",
        "security_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_security_events_occurred_at", table_name="security_events")
