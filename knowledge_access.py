"""Fail-closed authorization policy for project knowledge retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from permissions import canonical_role, role_can


KNOWLEDGE_READ_PERMISSION: Final = "knowledge.read"
GLOBAL_KNOWLEDGE_ROLES: Final[frozenset[str]] = frozenset(
    {"administrator", "supervisor"}
)

KnowledgeAccessScope = Literal["project", "global", "denied"]
KnowledgeAccessReason = Literal[
    "project_owner",
    "global_operator",
    "missing_permission",
    "outside_project",
]


@dataclass(frozen=True)
class KnowledgeAccessDecision:
    """The non-sensitive result of one project knowledge access decision."""

    allowed: bool
    scope: KnowledgeAccessScope
    reason: KnowledgeAccessReason


def evaluate_project_knowledge_access(
    actor_id: UUID,
    actor_role: str,
    project_owner_id: UUID,
) -> KnowledgeAccessDecision:
    """Evaluate the complete read boundary before retrieval begins.

    The route-level permission dependency remains the first authorization
    gate.  Repeating that check here keeps this policy fail-closed when it is
    reused by another retrieval entry point.  The result contains no query,
    document, project title, or other sensitive request data.
    """

    if not role_can(actor_role, KNOWLEDGE_READ_PERMISSION):
        return KnowledgeAccessDecision(
            allowed=False,
            scope="denied",
            reason="missing_permission",
        )

    if canonical_role(actor_role) in GLOBAL_KNOWLEDGE_ROLES:
        return KnowledgeAccessDecision(
            allowed=True,
            scope="global",
            reason="global_operator",
        )

    if actor_id == project_owner_id:
        return KnowledgeAccessDecision(
            allowed=True,
            scope="project",
            reason="project_owner",
        )

    return KnowledgeAccessDecision(
        allowed=False,
        scope="denied",
        reason="outside_project",
    )


__all__ = [
    "GLOBAL_KNOWLEDGE_ROLES",
    "KNOWLEDGE_READ_PERMISSION",
    "KnowledgeAccessDecision",
    "KnowledgeAccessReason",
    "KnowledgeAccessScope",
    "evaluate_project_knowledge_access",
]
