"""Guarded specialist-agent rules for the local workflow prototype.

The project does not execute arbitrary model code or shell commands.  This
module defines the small specialist-agent registry, the permitted handoff
edges, and the validation boundary used before and after a handoff runs.
Inputs are treated as untrusted data and persisted only as a fingerprint and
safe summary.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Final, Literal

from knowledge_security import scan_prompt_injection

AgentName = Literal["intake", "research", "knowledge", "quality_control"]
AgentActorName = Literal[
    "orchestrator",
    "intake",
    "research",
    "knowledge",
    "quality_control",
]

AGENT_NAMES: Final[tuple[str, ...]] = (
    "intake",
    "research",
    "knowledge",
    "quality_control",
)
AGENT_ACTOR_NAMES: Final[tuple[str, ...]] = ("orchestrator", *AGENT_NAMES)
AGENT_HANDOFF_STATUSES: Final[tuple[str, ...]] = ("completed", "blocked", "failed")
MAX_AGENT_INPUT_CHARACTERS: Final[int] = 500
MAX_AGENT_OUTPUT_KEYS: Final[int] = 12
MAX_AGENT_TRACE_RESULTS: Final[int] = 50
MAX_AGENT_METRIC_VALUE: Final[int] = 1_000_000
AGENT_RESULT_KEYS: Final[frozenset[str]] = frozenset(
    {"agent", "status", "summary", "metrics", "tool"}
)
_WINDOWS_ABSOLUTE_PATH: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z]:/")
_APPROVAL_BYPASS: Final[re.Pattern[str]] = re.compile(
    r"(?:\b(?:bypass|skip|disable|ignore|override|without)\b.{0,80}\b"
    r"(?:human\s+)?(?:approval|review(?:er)?|approval\s+gate)\b|"
    r"\b(?:approval|human\s+review|reviewer)\b.{0,80}\b"
    r"(?:bypass|skip|disable|ignore|override)\b)",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT: Final[re.Pattern[str]] = re.compile(
    r"\b(?:password|passwd|secret|api[ _-]?key|access[ _-]?token|credential)"
    r"\b\s*[:=]\s*\S{4,}",
    re.IGNORECASE,
)
_AGENT_METRIC_TYPES: Final[dict[str, dict[str, type]]] = {
    "intake": {
        "intake_complete": bool,
        "missing_field_count": int,
        "output_count": int,
    },
    "research": {
        "review_count": int,
        "needs_review": int,
        "changes_requested": int,
        "verified": int,
        "approved": int,
    },
    "knowledge": {
        "source_count": int,
        "approved_source_count": int,
        "pending_source_count": int,
        "rejected_source_count": int,
    },
    "quality_control": {
        "workflow_state": str,
        "pending_approval_count": int,
        "pending_action_count": int,
        "failed_tool_count": int,
    },
}
_WORKFLOW_STATE_VALUES: Final[frozenset[str]] = frozenset(
    {"ready", "in_progress", "review", "changes_required", "approved", "archived"}
)


@dataclass(frozen=True)
class AgentDefinition:
    """One specialist's responsibility and least-privilege tool boundary."""

    agent: str
    label: str
    responsibility: str
    allowed_tools: tuple[str, ...]
    handoff_targets: tuple[str, ...]


AGENT_DEFINITIONS: Final[tuple[AgentDefinition, ...]] = (
    AgentDefinition(
        agent="intake",
        label="Intake specialist",
        responsibility="Check the project brief, scope, owner, deadline, and expected outputs.",
        allowed_tools=(),
        handoff_targets=("research", "knowledge"),
    ),
    AgentDefinition(
        agent="research",
        label="Research specialist",
        responsibility="Summarize evidence-review state and surface claims that still need attention.",
        allowed_tools=("research.summary",),
        handoff_targets=("quality_control",),
    ),
    AgentDefinition(
        agent="knowledge",
        label="Knowledge specialist",
        responsibility="Work only with approved project knowledge and report source readiness.",
        allowed_tools=("knowledge.search",),
        handoff_targets=("quality_control",),
    ),
    AgentDefinition(
        agent="quality_control",
        label="Quality-control specialist",
        responsibility="Check workflow readiness, outstanding reviews, and approval blockers.",
        allowed_tools=("files.summary", "research.summary"),
        handoff_targets=(),
    ),
)

AGENT_DEFINITION_BY_NAME: Final[dict[str, AgentDefinition]] = {
    definition.agent: definition for definition in AGENT_DEFINITIONS
}


class AgentInputBlockedError(ValueError):
    """Raised when a handoff input matches a known unsafe pattern."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__("Agent input was blocked by a safety rule.")


def get_agent_definition(agent: str) -> AgentDefinition | None:
    """Return an allow-listed specialist definition."""

    return AGENT_DEFINITION_BY_NAME.get(agent)


def can_delegate(source_agent: str, target_agent: str) -> bool:
    """Return whether one declared specialist may hand off to another."""

    if target_agent not in AGENT_DEFINITION_BY_NAME:
        return False
    if source_agent == "orchestrator":
        return True
    source = get_agent_definition(source_agent)
    return source is not None and target_agent in source.handoff_targets


def handoff_event_code(status: str) -> str:
    """Return the stable audit event code for one persisted handoff outcome."""

    if status not in AGENT_HANDOFF_STATUSES:
        raise ValueError("Unknown specialist handoff status.")
    return f"agent.handoff.{status}"


def validate_agent_input(input_ref: str | None) -> str | None:
    """Validate bounded, untrusted handoff context without treating it as code."""

    if input_ref is None:
        return None
    normalized = input_ref.strip()
    if not normalized:
        raise ValueError("Agent input must not be blank.")
    if len(normalized) > MAX_AGENT_INPUT_CHARACTERS:
        raise ValueError("Agent input is too long.")
    if "\x00" in normalized or "\\" in normalized:
        raise ValueError("Agent input contains an unsafe path character.")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError("Agent input contains an unsafe control character.")
    if (
        normalized.startswith("/")
        or _WINDOWS_ABSOLUTE_PATH.match(normalized)
        or any(segment in {".", ".."} for segment in normalized.split("/"))
    ):
        raise ValueError("Agent input must not contain an absolute or traversal path.")

    findings = scan_prompt_injection(normalized)
    if findings:
        raise AgentInputBlockedError(findings[0].rule_id)
    if _APPROVAL_BYPASS.search(normalized):
        raise AgentInputBlockedError("approval-bypass")
    return normalized


def input_fingerprint(input_ref: str | None) -> str:
    """Return a SHA-256 trace digest without persisting raw context."""

    value = (input_ref or "").encode("utf-8")
    return sha256(value).hexdigest()


def input_summary(input_ref: str | None) -> str:
    """Return a safe trace summary that contains no user-supplied text."""

    if input_ref is None:
        return "input_supplied:false"
    return f"input_supplied:true sha256_prefix:{input_fingerprint(input_ref)[:16]}"


def validate_agent_result(
    agent: str, result: Mapping[str, object]
) -> dict[str, object]:
    """Validate the structured result boundary before it is persisted."""

    unexpected_keys = set(result) - AGENT_RESULT_KEYS
    if unexpected_keys:
        raise ValueError("Agent result contains unknown fields.")
    if agent not in AGENT_DEFINITION_BY_NAME:
        raise ValueError("Agent result names an unknown specialist.")
    if result.get("agent") != agent:
        raise ValueError("Agent result does not match the requested specialist.")
    if result.get("status") != "completed":
        raise ValueError("Agent result has an invalid completion status.")
    summary = result.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 500:
        raise ValueError("Agent result summary is malformed.")
    if scan_prompt_injection(summary):
        raise ValueError("Agent result summary contains unsafe instruction patterns.")
    if _SECRET_ASSIGNMENT.search(summary):
        raise ValueError("Agent result summary contains credential-like material.")

    definition = AGENT_DEFINITION_BY_NAME[agent]
    tool = result.get("tool")
    if tool is not None and (
        not isinstance(tool, str) or tool not in definition.allowed_tools
    ):
        raise ValueError("Agent result names a tool outside its permission boundary.")
    if len(definition.allowed_tools) == 1 and tool != definition.allowed_tools[0]:
        raise ValueError("Agent result must identify its permitted tool.")

    metrics = result.get("metrics")
    if not isinstance(metrics, dict) or len(metrics) > MAX_AGENT_OUTPUT_KEYS:
        raise ValueError("Agent result metrics are malformed.")
    for key, value in metrics.items():
        if not isinstance(key, str) or len(key) > 64:
            raise ValueError("Agent result metric names are malformed.")
        if isinstance(value, (dict, list, tuple)):
            raise TypeError("Agent result metrics must be scalar values.")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Agent result metrics must contain finite numbers.")
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise ValueError("Agent result metrics contain an unsupported value.")
        if any(
            secret_word in key.lower()
            for secret_word in ("secret", "token", "password", "credential")
        ):
            raise ValueError("Agent result cannot contain secret-bearing metrics.")

    metric_types = _AGENT_METRIC_TYPES[agent]
    if set(metrics) != set(metric_types):
        raise ValueError("Agent result metrics do not match the specialist schema.")
    for key, expected_type in metric_types.items():
        value = metrics[key]
        if expected_type is bool:
            if type(value) is not bool:
                raise ValueError("Agent result boolean metrics are malformed.")
        elif expected_type is int:
            if type(value) is not int or not 0 <= value <= MAX_AGENT_METRIC_VALUE:
                raise ValueError(
                    "Agent result count metrics must be bounded nonnegative integers."
                )
        elif expected_type is str and (
            type(value) is not str
            or key != "workflow_state"
            or value not in _WORKFLOW_STATE_VALUES
        ):
            raise ValueError("Agent result state metric is not allow-listed.")
    return dict(result)


__all__ = [
    "AGENT_ACTOR_NAMES",
    "AGENT_DEFINITIONS",
    "AGENT_HANDOFF_STATUSES",
    "AGENT_NAMES",
    "AGENT_RESULT_KEYS",
    "MAX_AGENT_TRACE_RESULTS",
    "AgentDefinition",
    "AgentInputBlockedError",
    "AgentName",
    "can_delegate",
    "get_agent_definition",
    "handoff_event_code",
    "input_fingerprint",
    "input_summary",
    "validate_agent_input",
    "validate_agent_result",
]
