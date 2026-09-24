"""Defence-in-depth checks for untrusted knowledge content.

Knowledge documents and user questions are data, not application instructions.
This module deliberately returns rule identifiers only; matched document text is
never included in exceptions, audit records, or evaluation output.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Final, Literal, Pattern


PromptInjectionCategory = Literal[
    "instruction_override",
    "secret_exfiltration",
    "access_boundary_bypass",
]


@dataclass(frozen=True)
class PromptInjectionFinding:
    """One bounded classification for a suspicious untrusted-text pattern."""

    rule_id: str
    category: PromptInjectionCategory


@dataclass(frozen=True)
class _PromptInjectionRule:
    rule_id: str
    category: PromptInjectionCategory
    pattern: Pattern[str]


class UnsafeKnowledgeContentError(ValueError):
    """Raised when a document contains an instruction-shaped attack pattern."""

    def __init__(self, findings: tuple[PromptInjectionFinding, ...]) -> None:
        self.findings = findings
        super().__init__("Document contains unsafe instruction patterns.")


_PROMPT_INJECTION_RULES: Final[tuple[_PromptInjectionRule, ...]] = (
    _PromptInjectionRule(
        "instruction-override",
        "instruction_override",
        re.compile(
            r"(?:^|[.!?;:\n])\s*"
            r"(?:ignore|disregard|forget|override)\b.{0,120}\b"
            r"(?:instructions?|rules?|policy|prompt)\b",
            re.IGNORECASE,
        ),
    ),
    _PromptInjectionRule(
        "secret-exfiltration",
        "secret_exfiltration",
        re.compile(
            r"(?:^|[.!?;:\n])\s*"
            r"(?:(?:please|kindly)\s+|(?:can|could|would)\s+you\s+(?:please\s+)?|"
            r"(?:i\s+need|i\s+want)\s+you\s+to\s+)?"
            r"(?:reveal|disclose|dump|print|exfiltrate|share|show|return)\b"
            r".{0,120}\b(?:system\s+prompt|developer\s+message|secrets?|"
            r"credentials?|passwords?|api\s+keys?|access\s+tokens?|"
            r"recovery\s+codes?)\b",
            re.IGNORECASE,
        ),
    ),
    _PromptInjectionRule(
        "access-boundary-bypass",
        "access_boundary_bypass",
        re.compile(
            r"(?:^|[.!?;:\n])\s*"
            r"(?:bypass|circumvent|evade|override)\b.{0,120}\b"
            r"(?:project|tenant|permission|role|access)\b"
            r"|(?:^|[.!?;:\n])\s*"
            r"(?:grant|give|allow)\b.{0,80}\b(?:access|permission)\b"
            r".{0,80}\b(?:another|other|all)\s+projects?\b",
            re.IGNORECASE,
        ),
    ),
)


def scan_prompt_injection(text: str) -> tuple[PromptInjectionFinding, ...]:
    """Return classifications for explicit injection-shaped instructions."""

    if not text.strip():
        return ()
    return tuple(
        PromptInjectionFinding(rule.rule_id, rule.category)
        for rule in _PROMPT_INJECTION_RULES
        if rule.pattern.search(text)
    )


def is_safe_untrusted_text(text: str) -> bool:
    """Return whether text contains no known instruction-shaped attack."""

    return not scan_prompt_injection(text)


def ensure_safe_untrusted_text(text: str) -> None:
    """Raise a bounded error when text should not enter the knowledge index."""

    findings = scan_prompt_injection(text)
    if findings:
        raise UnsafeKnowledgeContentError(findings)


__all__ = [
    "PromptInjectionCategory",
    "PromptInjectionFinding",
    "UnsafeKnowledgeContentError",
    "ensure_safe_untrusted_text",
    "is_safe_untrusted_text",
    "scan_prompt_injection",
]
