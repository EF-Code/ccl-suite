"""Constrain persisted handoff actors to the specialist registry."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0013_agent_actor_constraints"
down_revision: str | Sequence[str] | None = "0012_multi_agent_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SOURCE_ACTORS = "'orchestrator', 'intake', 'research', 'knowledge', 'quality_control'"
_TARGET_AGENTS = "'intake', 'research', 'knowledge', 'quality_control'"


def upgrade() -> None:
    with op.batch_alter_table("agent_handoffs", recreate="always") as batch_op:
        batch_op.create_check_constraint(
            "ck_agent_handoffs_source_agent_allowlist",
            f"source_agent IN ({_SOURCE_ACTORS})",
        )
        batch_op.create_check_constraint(
            "ck_agent_handoffs_target_agent_allowlist",
            f"target_agent IN ({_TARGET_AGENTS})",
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_handoffs", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "ck_agent_handoffs_target_agent_allowlist",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_agent_handoffs_source_agent_allowlist",
            type_="check",
        )
