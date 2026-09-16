"""Bounded, deterministic research-evidence extraction and scope checks.

This module implements the first research-evidence boundary without an
external model.  Source text is treated as untrusted data, exact source
passages are carried forward for review, and applicability comparisons are
deliberately conservative: an absent or unclear scope value becomes
``uncertain`` rather than being inferred.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
import re
from typing import Final, Literal
from uuid import UUID, uuid4

from knowledge_security import ensure_safe_untrusted_text


RESEARCH_EVIDENCE_SCHEMA_VERSION: Final = "research-evidence-v1"
MAX_RESEARCH_SOURCE_CHARACTERS: Final = 20_000
MAX_RESEARCH_CLAIMS: Final = 100
MAX_RESEARCH_CLAIM_CHARACTERS: Final = 500
MAX_RESEARCH_SCOPE_VALUE_CHARACTERS: Final = 120

ClaimClassification = Literal[
    "factual",
    "heading",
    "instruction",
    "opinion",
    "creative",
]
ReviewStatus = Literal["needs_review"]
ApplicabilityFieldName = Literal[
    "model_year",
    "engine",
    "market",
    "population",
    "setting",
    "evidence_type",
]
ApplicabilityFieldStatus = Literal[
    "match",
    "mismatch",
    "uncertain",
    "not_requested",
]
ApplicabilityStatus = Literal[
    "applicable",
    "mismatch",
    "uncertain",
    "not_applicable",
]
ScopeValue = str | int | None

RESEARCH_SCOPE_FIELDS: Final[tuple[ApplicabilityFieldName, ...]] = (
    "model_year",
    "engine",
    "market",
    "population",
    "setting",
    "evidence_type",
)


class ResearchEvidenceError(ValueError):
    """Raised when bounded evidence processing cannot safely continue."""


@dataclass(frozen=True)
class ExtractedClaim:
    """One classified claim with enough provenance for a later review step."""

    claim_id: UUID
    claim: str
    classification: ClaimClassification
    source_title: str
    source_reference: str
    source_date: date | None
    passage: str
    scope: Mapping[str, ScopeValue]
    review_status: ReviewStatus = "needs_review"


@dataclass(frozen=True)
class ApplicabilityFieldResult:
    """One field-level comparison made by the conservative scope checker."""

    field: ApplicabilityFieldName
    status: ApplicabilityFieldStatus
    requested: str | None
    observed: str | None


@dataclass(frozen=True)
class ApplicabilityResult:
    """The overall scope decision plus its auditable field comparisons."""

    claim_id: UUID
    claim_classification: ClaimClassification
    status: ApplicabilityStatus
    reason: str
    fields: tuple[ApplicabilityFieldResult, ...]


_HEADING_PATTERN: Final = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_BULLET_PATTERN: Final = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s+)")
_SENTENCE_BOUNDARY: Final = re.compile(r"(?<=[.!?])\s+")
_INSTRUCTION_PATTERN: Final = re.compile(
    r"^(?:always|avoid|check|choose|do not|don't|ensure|follow|keep|never|"
    r"record|review|save|send|submit|use|verify|write)\b|"
    r"\b(?:must|should|need to)\b",
    re.IGNORECASE,
)
_OPINION_PATTERN: Final = re.compile(
    r"^(?:i think|we believe|in my opinion|probably|likely|arguably|"
    r"it seems|may be|might be|we expect)\b|"
    r"\b(?:probably|likely|arguably|may|might)\b",
    re.IGNORECASE,
)
_CREATIVE_PATTERN: Final = re.compile(
    r"^(?:script|scene|caption|hook|voiceover|voice-over|title|dialogue|"
    r"shot|b-roll|on-screen text|prompt|storyboard|thumbnail|visual direction)"
    r"\s*[:\-]\s*",
    re.IGNORECASE,
)
_UNKNOWN_SCOPE_VALUES: Final = frozenset(
    {
        "",
        "unknown",
        "unspecified",
        "not specified",
        "not provided",
        "n/a",
        "na",
        "none",
    }
)
_WILDCARD_SCOPE_VALUES: Final = frozenset(
    {"all", "any", "global", "worldwide", "all markets", "all populations"}
)
def _bounded_source_text(value: str) -> str:
    """Normalize source line endings while preserving all source characters."""

    if len(value) > MAX_RESEARCH_SOURCE_CHARACTERS:
        raise ResearchEvidenceError("Source is larger than the evidence limit.")
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _safe_scope(scope: Mapping[str, ScopeValue]) -> dict[str, ScopeValue]:
    """Keep only supported scope fields and reject unsafe/oversized strings."""

    safe_scope: dict[str, ScopeValue] = {}
    for field in RESEARCH_SCOPE_FIELDS:
        value = scope.get(field)
        if isinstance(value, str):
            if len(value) > MAX_RESEARCH_SCOPE_VALUE_CHARACTERS:
                raise ResearchEvidenceError("Scope value is larger than the evidence limit.")
            ensure_safe_untrusted_text(value)
        safe_scope[field] = value
    return safe_scope


def _claim_text_from_line(line: str) -> str:
    """Remove Markdown list decoration for classification, not for passage."""

    return _BULLET_PATTERN.sub("", line).strip()


def _heading_text(line: str) -> str | None:
    match = _HEADING_PATTERN.match(line)
    if match is None:
        return None
    return match.group(1).strip()


def classify_claim(text: str, *, is_heading: bool = False) -> ClaimClassification:
    """Classify one bounded text unit without interpreting its meaning."""

    candidate = text.strip()
    if is_heading:
        return "heading"
    if _CREATIVE_PATTERN.match(candidate):
        return "creative"
    if _OPINION_PATTERN.search(candidate):
        return "opinion"
    if _INSTRUCTION_PATTERN.search(candidate):
        return "instruction"
    return "factual"


def research_scope_fields() -> tuple[ApplicabilityFieldName, ...]:
    """Return the stable order used by every scope report."""

    return RESEARCH_SCOPE_FIELDS


def _claim_units(line: str) -> list[str]:
    """Split a source line into sentence-sized claim candidates."""

    candidate = _claim_text_from_line(line)
    if not candidate:
        return []
    units = [unit.strip() for unit in _SENTENCE_BOUNDARY.split(candidate) if unit.strip()]
    return units or [candidate]


def extract_claims(
    source_text: str,
    *,
    source_title: str,
    source_reference: str,
    source_date: date | None = None,
    scope: Mapping[str, ScopeValue] | None = None,
) -> tuple[ExtractedClaim, ...]:
    """Extract bounded claims while retaining each exact source line passage.

    This is intentionally not a semantic claim generator.  It classifies
    source-shaped text and never invents a claim, source, date, or scope.
    """

    ensure_safe_untrusted_text(source_title)
    ensure_safe_untrusted_text(source_reference)
    normalized_source = _bounded_source_text(source_text)
    ensure_safe_untrusted_text(normalized_source)
    safe_scope = _safe_scope(scope or {})

    claims: list[ExtractedClaim] = []
    for raw_line in normalized_source.split("\n"):
        passage = raw_line.strip()
        if not passage:
            continue
        heading = _heading_text(passage)
        if heading is not None:
            units = [(heading, True)]
        else:
            units = [(unit, False) for unit in _claim_units(passage)]

        for unit, is_heading in units:
            claim = unit.strip()
            if not claim:
                continue
            if len(claim) > MAX_RESEARCH_CLAIM_CHARACTERS:
                claim = claim[: MAX_RESEARCH_CLAIM_CHARACTERS - 1].rstrip() + "…"
            claims.append(
                ExtractedClaim(
                    claim_id=uuid4(),
                    claim=claim,
                    classification=classify_claim(unit, is_heading=is_heading),
                    source_title=source_title,
                    source_reference=source_reference,
                    source_date=source_date,
                    passage=passage,
                    scope=safe_scope,
                )
            )
            if len(claims) > MAX_RESEARCH_CLAIMS:
                raise ResearchEvidenceError("Source produced too many claims.")

    return tuple(claims)


def _scope_value(value: ScopeValue) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _scope_status(observed: ScopeValue, requested: ScopeValue) -> tuple[ApplicabilityFieldStatus, str | None, str | None]:
    """Compare one field using exact matching and explicit wildcards only."""

    requested_text = _scope_value(requested)
    observed_text = _scope_value(observed)
    if requested_text is None:
        return "not_requested", None, observed_text
    if observed_text is None or observed_text.casefold() in _UNKNOWN_SCOPE_VALUES:
        return "uncertain", requested_text, observed_text
    if observed_text.casefold() in _WILDCARD_SCOPE_VALUES:
        return "match", requested_text, observed_text
    if observed_text.casefold() == requested_text.casefold():
        return "match", requested_text, observed_text
    return "mismatch", requested_text, observed_text


def check_claim_applicability(
    claim_id: UUID,
    claim_classification: ClaimClassification,
    *,
    source_scope: Mapping[str, ScopeValue],
    target_scope: Mapping[str, ScopeValue],
) -> ApplicabilityResult:
    """Check configured applicability fields without guessing missing context."""

    safe_source_scope = _safe_scope(source_scope)
    safe_target_scope = _safe_scope(target_scope)
    if claim_classification != "factual":
        return ApplicabilityResult(
            claim_id=claim_id,
            claim_classification=claim_classification,
            status="not_applicable",
            reason="Only factual claims are eligible for applicability checking.",
            fields=tuple(
                ApplicabilityFieldResult(field=field, status="not_requested", requested=None, observed=_scope_value(safe_source_scope.get(field)))
                for field in RESEARCH_SCOPE_FIELDS
            ),
        )

    fields = tuple(
        ApplicabilityFieldResult(
            field=field,
            status=status_value,
            requested=requested,
            observed=observed,
        )
        for field in RESEARCH_SCOPE_FIELDS
        for status_value, requested, observed in (
            _scope_status(safe_source_scope.get(field), safe_target_scope.get(field)),
        )
    )
    requested_fields = [field for field in fields if field.status != "not_requested"]
    if not requested_fields:
        status: ApplicabilityStatus = "uncertain"
        reason = "No target scope was provided; applicability cannot be established."
    elif any(field.status == "mismatch" for field in requested_fields):
        status = "mismatch"
        reason = "At least one requested scope field does not match the source."
    elif any(field.status == "uncertain" for field in requested_fields):
        status = "uncertain"
        reason = "A requested scope field is missing or unclear in the source."
    else:
        status = "applicable"
        reason = "All requested scope fields match the source."

    return ApplicabilityResult(
        claim_id=claim_id,
        claim_classification=claim_classification,
        status=status,
        reason=reason,
        fields=fields,
    )


__all__ = [
    "ApplicabilityFieldName",
    "ApplicabilityFieldResult",
    "ApplicabilityResult",
    "ApplicabilityStatus",
    "ClaimClassification",
    "ExtractedClaim",
    "MAX_RESEARCH_CLAIMS",
    "MAX_RESEARCH_CLAIM_CHARACTERS",
    "MAX_RESEARCH_SOURCE_CHARACTERS",
    "RESEARCH_EVIDENCE_SCHEMA_VERSION",
    "RESEARCH_SCOPE_FIELDS",
    "ResearchEvidenceError",
    "check_claim_applicability",
    "classify_claim",
    "extract_claims",
    "research_scope_fields",
]
