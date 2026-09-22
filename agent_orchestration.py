"""Guarded specialist-agent rules for the local workflow prototype.

The project does not execute arbitrary model code or shell commands.  This
module defines the small specialist-agent registry, the permitted handoff
edges, and the validation boundary used before and after a handoff runs.
Inputs are treated as untrusted data and persisted only as a fingerprint and
safe summary.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import math
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
MAX_AGENT_INPUT_CHARACTERS: Final[int] = 500
MAX_AGENT_OUTPUT_KEYS: Final[int] = 12
MAX_AGENT_TRACE_RESULTS: Final[int] = 50
AGENT_RESULT_KEYS: Final[frozenset[str]] = frozenset(
    {"agent", "status", "summary", "metrics", "tool"}
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
    if normalized.startswith("/") or any(
        segment in {".", ".."} for segment in normalized.split("/")
    ):
        raise ValueError("Agent input must not contain an absolute or traversal path.")

    findings = scan_prompt_injection(normalized)
    if findings:
        raise AgentInputBlockedError(findings[0].rule_id)
    return normalized


def input_fingerprint(input_ref: str | None) -> str:
    """Return a non-reversible trace fingerprint instead of storing raw input."""

    value = (input_ref or "").encode("utf-8")
    return sha256(value).hexdigest()


def input_summary(input_ref: str | None) -> str:
    """Return a safe trace summary that contains no user-supplied text."""

    if input_ref is None:
        return "input_supplied:false"
    return f"input_supplied:true sha256_prefix:{input_fingerprint(input_ref)[:16]}"


def validate_agent_result(agent: str, result: Mapping[str, object]) -> dict[str, object]:
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
    metrics = result.get("metrics")
    if not isinstance(metrics, dict) or len(metrics) > MAX_AGENT_OUTPUT_KEYS:
        raise ValueError("Agent result metrics are malformed.")
    for key, value in metrics.items():
        if not isinstance(key, str) or len(key) > 64:
            raise ValueError("Agent result metric names are malformed.")
        if isinstance(value, (dict, list, tuple)):
            raise ValueError("Agent result metrics must be scalar values.")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Agent result metrics must contain finite numbers.")
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise ValueError("Agent result metrics contain an unsupported value.")
        if any(secret_word in key.lower() for secret_word in ("secret", "token", "password", "credential")):
            raise ValueError("Agent result cannot contain secret-bearing metrics.")
    return dict(result)


__all__ = [
    "AGENT_ACTOR_NAMES",
    "AGENT_DEFINITIONS",
    "AGENT_RESULT_KEYS",
    "AGENT_NAMES",
    "AgentDefinition",
    "AgentInputBlockedError",
    "AgentName",
    "MAX_AGENT_TRACE_RESULTS",
    "can_delegate",
    "get_agent_definition",
    "input_fingerprint",
    "input_summary",
    "validate_agent_input",
    "validate_agent_result",
]
