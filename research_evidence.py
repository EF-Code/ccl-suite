"""Bounded, deterministic research-evidence extraction and scope checks.

This module implements the first research-evidence boundary without an
external model.  Source text is treated as untrusted data, exact source
passages are carried forward for review, and applicability comparisons are
deliberately conservative: an absent or unclear scope value becomes
``uncertain`` rather than being inferred.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
EvidenceWarningCode = Literal[
    "missing_evidence",
    "source_mismatch",
    "duplicate_claim",
    "conflict",
    "unsupported_claim",
]
EvidenceWarningSeverity = Literal["error", "warning"]
EvidenceAssessmentStatus = Literal["supported", "needs_review", "not_applicable"]
EvidenceRegisterStatus = Literal["clear", "warnings"]

RESEARCH_SCOPE_FIELDS: Final[tuple[ApplicabilityFieldName, ...]] = (
    "model_year",
    "engine",
    "market",
    "population",
    "setting",
    "evidence_type",
)
EVIDENCE_WARNING_CODES: Final[tuple[EvidenceWarningCode, ...]] = (
    "missing_evidence",
    "source_mismatch",
    "duplicate_claim",
    "conflict",
    "unsupported_claim",
)
MAX_RESEARCH_WARNING_COUNT: Final = 500


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


@dataclass(frozen=True)
class EvidenceWarning:
    """One bounded, explainable issue found in an evidence register preview."""

    code: EvidenceWarningCode
    severity: EvidenceWarningSeverity
    claim_id: UUID
    message: str
    related_claim_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class EvidenceAssessment:
    """Automated support state for one claim without granting approval."""

    claim_id: UUID
    status: EvidenceAssessmentStatus
    warning_codes: tuple[EvidenceWarningCode, ...]


@dataclass(frozen=True)
class EvidenceRegisterResult:
    """Non-persisted register summary and warning list."""

    status: EvidenceRegisterStatus
    claim_count: int
    warning_count: int
    supported_count: int
    needs_review_count: int
    not_applicable_count: int
    assessments: tuple[EvidenceAssessment, ...]
    warnings: tuple[EvidenceWarning, ...]


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
        "not applicable",
    }
)
_WILDCARD_SCOPE_VALUES: Final = frozenset(
    {
        "*",
        "all",
        "any",
        "global",
        "worldwide",
        "all engines",
        "all markets",
        "all model years",
        "all populations",
        "all settings",
        "all evidence types",
    }
)
_MISSING_EVIDENCE_VALUES: Final = frozenset(
    {
        "",
        "unknown",
        "unspecified",
        "not specified",
        "not provided",
        "not available",
        "n/a",
        "na",
        "none",
    }
)
_NEGATION_WORDS: Final = frozenset({"not", "never", "no"})


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
        if not raw_line.strip():
            continue
        parsing_line = raw_line.strip()
        heading = _heading_text(parsing_line)
        if heading is not None:
            units = [(heading, True)]
        else:
            units = [(unit, False) for unit in _claim_units(parsing_line)]

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
                    passage=raw_line,
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


def _canonical_scope_text(value: str) -> str:
    """Compare text scopes without making semantic assumptions."""

    return " ".join(value.split()).casefold()


def _scope_status(observed: ScopeValue, requested: ScopeValue) -> tuple[ApplicabilityFieldStatus, str | None, str | None]:
    """Compare one field using exact matching and explicit wildcards only."""

    requested_text = _scope_value(requested)
    observed_text = _scope_value(observed)
    if requested_text is None:
        return "not_requested", None, observed_text
    observed_comparable = _canonical_scope_text(observed_text) if observed_text else None
    requested_comparable = _canonical_scope_text(requested_text)
    if requested_comparable in _UNKNOWN_SCOPE_VALUES:
        return "uncertain", requested_text, observed_text
    if observed_text is None or observed_comparable in _UNKNOWN_SCOPE_VALUES:
        return "uncertain", requested_text, observed_text
    if observed_comparable in _WILDCARD_SCOPE_VALUES:
        return "match", requested_text, observed_text
    if observed_comparable == requested_comparable:
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


def _canonical_evidence_text(value: str) -> str:
    """Normalize whitespace and case without making semantic assumptions."""

    return " ".join(value.split()).casefold()


def _canonical_claim_text(value: str) -> str:
    """Normalize claim punctuation for exact, deterministic comparisons."""

    return " ".join(re.sub(r"[^\w\s']", " ", value.casefold()).split())


def _missing_evidence_value(value: str) -> bool:
    return _canonical_evidence_text(value) in _MISSING_EVIDENCE_VALUES


def _claim_is_in_passage(claim: ExtractedClaim) -> bool:
    claim_text = _canonical_claim_text(claim.claim)
    passage_text = _canonical_claim_text(claim.passage)
    return bool(claim_text) and claim_text in passage_text


def _simple_verb_stem(token: str) -> str:
    """Align only common third-person endings for conservative conflict checks."""

    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 4 and token.endswith("es"):
        return token[:-2] + "e"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _claim_polarity_signature(value: str) -> tuple[str, bool] | None:
    """Return a narrow polarity signature for explicit positive/negative pairs."""

    normalized = value.casefold().replace("doesn't", "does not").replace("isn't", "is not")
    normalized = normalized.replace("aren't", "are not").replace("can't", "can not")
    tokens = re.findall(r"[a-z0-9']+", normalized)
    if not tokens:
        return None

    negative = False
    base_tokens: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"does", "do", "did"} and index + 1 < len(tokens) and tokens[index + 1] == "not":
            negative = True
            index += 2
            continue
        if token in _NEGATION_WORDS:
            negative = True
            index += 1
            continue
        if token == "cannot":
            negative = True
            index += 1
            continue
        base_tokens.append(_simple_verb_stem(token))
        index += 1

    signature = " ".join(base_tokens)
    return (signature, negative) if signature else None


def _append_warning(
    warnings: list[EvidenceWarning],
    warning: EvidenceWarning,
) -> None:
    """Keep the register bounded before it reaches an API response."""

    warnings.append(warning)
    if len(warnings) > MAX_RESEARCH_WARNING_COUNT:
        raise ResearchEvidenceError("Evidence register produced too many warnings.")


def build_evidence_register(
    claims: Sequence[ExtractedClaim],
    *,
    expected_source_title: str | None = None,
    expected_source_reference: str | None = None,
    target_scope: Mapping[str, ScopeValue] | None = None,
) -> EvidenceRegisterResult:
    """Run bounded completeness and consistency checks over claim previews.

    This function deliberately reports warnings instead of approving evidence.
    It compares supplied metadata and explicit text only; semantic support is
    never inferred from a claim's wording.
    """

    if not claims:
        raise ResearchEvidenceError("At least one claim is required for a register.")
    if len(claims) > MAX_RESEARCH_CLAIMS:
        raise ResearchEvidenceError("Evidence register contains too many claims.")

    claim_ids = [claim.claim_id for claim in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise ResearchEvidenceError("Evidence register claim IDs must be unique.")

    if expected_source_title is not None:
        ensure_safe_untrusted_text(expected_source_title)
    if expected_source_reference is not None:
        ensure_safe_untrusted_text(expected_source_reference)
    safe_target_scope = _safe_scope(target_scope or {})
    target_requested = any(value is not None for value in safe_target_scope.values())

    warnings: list[EvidenceWarning] = []
    warning_codes_by_claim: dict[UUID, list[EvidenceWarningCode]] = {
        claim.claim_id: [] for claim in claims
    }

    def add_claim_warning(
        claim: ExtractedClaim,
        *,
        code: EvidenceWarningCode,
        severity: EvidenceWarningSeverity,
        message: str,
        related_claim_ids: tuple[UUID, ...] = (),
    ) -> None:
        if code not in warning_codes_by_claim[claim.claim_id]:
            warning_codes_by_claim[claim.claim_id].append(code)
        _append_warning(
            warnings,
            EvidenceWarning(
                code=code,
                severity=severity,
                claim_id=claim.claim_id,
                message=message,
                related_claim_ids=related_claim_ids,
            ),
        )

    duplicate_groups: dict[str, list[ExtractedClaim]] = {}
    polarity_groups: dict[str, dict[bool, list[ExtractedClaim]]] = {}

    for claim in claims:
        ensure_safe_untrusted_text(claim.claim)
        ensure_safe_untrusted_text(claim.source_title)
        ensure_safe_untrusted_text(claim.source_reference)
        ensure_safe_untrusted_text(claim.passage)
        _safe_scope(claim.scope)
        if claim.classification != "factual":
            continue

        duplicate_groups.setdefault(_canonical_claim_text(claim.claim), []).append(claim)
        polarity = _claim_polarity_signature(claim.claim)
        if polarity is not None:
            signature, negative = polarity
            polarity_groups.setdefault(signature, {True: [], False: []})[negative].append(claim)

        missing_fields = [
            field
            for field, value in (
                ("source title", claim.source_title),
                ("source reference", claim.source_reference),
                ("source passage", claim.passage),
            )
            if _missing_evidence_value(value)
        ]
        if missing_fields:
            add_claim_warning(
                claim,
                code="missing_evidence",
                severity="error",
                message=f"Missing usable {', '.join(missing_fields)}.",
            )
        elif not _claim_is_in_passage(claim):
            add_claim_warning(
                claim,
                code="unsupported_claim",
                severity="error",
                message="The factual claim is not present in its exact source passage.",
            )

        if expected_source_title is not None and _canonical_evidence_text(claim.source_title) != _canonical_evidence_text(expected_source_title):
            add_claim_warning(
                claim,
                code="source_mismatch",
                severity="warning",
                message="Claim source title does not match the register source.",
            )
        if expected_source_reference is not None and _canonical_evidence_text(claim.source_reference) != _canonical_evidence_text(expected_source_reference):
            add_claim_warning(
                claim,
                code="source_mismatch",
                severity="warning",
                message="Claim source reference does not match the register source.",
            )

        if target_requested:
            applicability = check_claim_applicability(
                claim.claim_id,
                claim.classification,
                source_scope=claim.scope,
                target_scope=safe_target_scope,
            )
            if applicability.status == "mismatch":
                add_claim_warning(
                    claim,
                    code="source_mismatch",
                    severity="warning",
                    message="Source scope does not match the requested target context.",
                )
            elif applicability.status == "uncertain":
                add_claim_warning(
                    claim,
                    code="missing_evidence",
                    severity="error",
                    message="Source scope is incomplete for the requested target context.",
                )

    for group in duplicate_groups.values():
        if len(group) < 2:
            continue
        related_ids = tuple(claim.claim_id for claim in group)
        for claim in group:
            add_claim_warning(
                claim,
                code="duplicate_claim",
                severity="warning",
                message="This factual claim is duplicated in the register.",
                related_claim_ids=related_ids,
            )

    for polarity_group in polarity_groups.values():
        if not polarity_group[True] or not polarity_group[False]:
            continue
        conflicting_claims = polarity_group[True] + polarity_group[False]
        for claim in conflicting_claims:
            related_ids = tuple(
                other.claim_id for other in conflicting_claims if other.claim_id != claim.claim_id
            )
            add_claim_warning(
                claim,
                code="conflict",
                severity="error",
                message="This factual claim conflicts with another claim in the register.",
                related_claim_ids=related_ids,
            )

    assessments: list[EvidenceAssessment] = []
    for claim in claims:
        claim_warning_codes = tuple(warning_codes_by_claim[claim.claim_id])
        if claim.classification != "factual":
            assessment_status: EvidenceAssessmentStatus = "not_applicable"
        elif claim_warning_codes:
            assessment_status = "needs_review"
        else:
            assessment_status = "supported"
        assessments.append(
            EvidenceAssessment(
                claim_id=claim.claim_id,
                status=assessment_status,
                warning_codes=claim_warning_codes,
            )
        )

    supported_count = sum(assessment.status == "supported" for assessment in assessments)
    needs_review_count = sum(assessment.status == "needs_review" for assessment in assessments)
    not_applicable_count = sum(assessment.status == "not_applicable" for assessment in assessments)
    return EvidenceRegisterResult(
        status="warnings" if warnings else "clear",
        claim_count=len(claims),
        warning_count=len(warnings),
        supported_count=supported_count,
        needs_review_count=needs_review_count,
        not_applicable_count=not_applicable_count,
        assessments=tuple(assessments),
        warnings=tuple(warnings),
    )


__all__ = [
    "EVIDENCE_WARNING_CODES",
    "EvidenceAssessment",
    "EvidenceAssessmentStatus",
    "EvidenceRegisterResult",
    "EvidenceRegisterStatus",
    "EvidenceWarning",
    "EvidenceWarningCode",
    "EvidenceWarningSeverity",
    "ApplicabilityFieldName",
    "ApplicabilityFieldResult",
    "ApplicabilityResult",
    "ApplicabilityStatus",
    "ClaimClassification",
    "ExtractedClaim",
    "MAX_RESEARCH_CLAIMS",
    "MAX_RESEARCH_CLAIM_CHARACTERS",
    "MAX_RESEARCH_SOURCE_CHARACTERS",
    "MAX_RESEARCH_WARNING_COUNT",
    "RESEARCH_EVIDENCE_SCHEMA_VERSION",
    "RESEARCH_SCOPE_FIELDS",
    "ResearchEvidenceError",
    "check_claim_applicability",
    "build_evidence_register",
    "classify_claim",
    "extract_claims",
    "research_scope_fields",
]
