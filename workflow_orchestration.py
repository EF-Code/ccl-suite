"""Bounded workflow-orchestration rules shared by the API and dashboard.

The orchestrator deliberately stays local and deterministic for this milestone.
It validates state changes, names the read-only tools that may be called, and
keeps high-impact actions behind an explicit approval gate.  It does not run
arbitrary shell commands, accept free-form tool names, or silently retry a
mutation.
"""

from __future__ import annotations

from typing import Final

WORKFLOW_STATES: Final[tuple[str, ...]] = (
    "ready",
    "in_progress",
    "review",
    "changes_required",
    "approved",
    "archived",
)

WORKFLOW_STATE_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "ready": frozenset({"in_progress", "review"}),
    "in_progress": frozenset({"review"}),
    "review": frozenset({"changes_required", "approved"}),
    "changes_required": frozenset({"in_progress", "review"}),
    "approved": frozenset({"review", "archived"}),
    "archived": frozenset(),
}

WORKFLOW_TOOLS: Final[tuple[str, ...]] = (
    "files.summary",
    "knowledge.search",
    "research.summary",
)

HIGH_IMPACT_ACTIONS: Final[tuple[str, ...]] = (
    "send",
    "delete",
    "replace",
    "publish",
    "archive",
    "approve",
)

MAX_TOOL_ATTEMPTS: Final[int] = 3
MAX_WORKFLOW_TRACE_RESULTS: Final[int] = 50
APPROVAL_GATED_STATES: Final[frozenset[str]] = frozenset({"approved", "archived"})
TERMINAL_WORKFLOW_STATES: Final[frozenset[str]] = frozenset({"archived"})


def can_transition(current: str, target: str) -> bool:
    """Return whether a workflow may move between two explicit states."""

    return target in WORKFLOW_STATE_TRANSITIONS.get(current, frozenset())


def action_requires_approval(action_code: str) -> bool:
    """Return whether an action must pause for a human decision."""

    return action_code in HIGH_IMPACT_ACTIONS


def requires_human_approval(state: str) -> bool:
    """Return whether entering a state is reserved for the approval gate."""

    return state in APPROVAL_GATED_STATES


def is_terminal_state(state: str) -> bool:
    """Return whether a workflow state accepts no further transitions."""

    return state in TERMINAL_WORKFLOW_STATES


__all__ = [
    "HIGH_IMPACT_ACTIONS",
    "APPROVAL_GATED_STATES",
    "TERMINAL_WORKFLOW_STATES",
    "MAX_TOOL_ATTEMPTS",
    "MAX_WORKFLOW_TRACE_RESULTS",
    "WORKFLOW_STATES",
    "WORKFLOW_STATE_TRANSITIONS",
    "WORKFLOW_TOOLS",
    "action_requires_approval",
    "can_transition",
    "is_terminal_state",
    "requires_human_approval",
]
