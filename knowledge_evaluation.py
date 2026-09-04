"""Deterministic evaluation suite for evidence-grounded answers.

The suite evaluates the local extractive answer composer with a fixed, local
corpus.  It is intentionally not a claim of model-level reasoning: conflicting
facts are expected to be presented as separately cited evidence, not resolved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from api_schemas import SemanticSearchResult
from knowledge_answer import GroundedAnswer, compose_grounded_answer


EvaluationCategory = Literal["supported", "refusal", "conflict"]


@dataclass(frozen=True)
class EvaluationPassage:
    """One source-linked fixture passage used by a benchmark question."""

    title: str
    content: str
    score: float = 0.72
    heading: str = "Procedure"
    source_type: str = "sop"
    sensitivity: str = "internal"


@dataclass(frozen=True)
class EvaluationCase:
    """One fixed question with its allowed evidence and expected behavior."""

    case_id: str
    category: EvaluationCategory
    question: str
    passages: tuple[EvaluationPassage, ...]
    expected_status: Literal["answered", "refused"]
    expected_excerpts: tuple[str, ...] = ()
    expected_refusal_reason: Literal["unsupported_query", "insufficient_evidence"] | None = None


@dataclass(frozen=True)
class EvaluationResult:
    """The observed answer and whether it met the fixed evaluation contract."""

    case: EvaluationCase
    answer: GroundedAnswer
    passed: bool
    failure_reason: str | None


def _passage(title: str, sentence: str, *, score: float = 0.72) -> EvaluationPassage:
    return EvaluationPassage(title=title, content=f"# Procedure\n\n{sentence}", score=score)


_RESTORE = _passage("Restore SOP", "Verify file hashes before restoring a file.")
_ORIGINAL = _passage("Restore SOP", "Keep the original file intact during recovery.")
_QUARANTINE = _passage("Conflict SOP", "Move conflicting files to the quarantine folder for review.")
_INVENTORY = _passage("Inventory SOP", "Create JSON and CSV manifests after scanning project files.")
_CONVERSION = _passage("Conversion SOP", "Reject conversion when the destination path already exists.")
_APPROVAL = _passage("Knowledge Review SOP", "Approve a knowledge source before it is ingested.")
_ACCESS = _passage("Access Rules", "Only the project owner can retrieve project rules.")
_CHECKSUM = _passage("Integrity SOP", "Use SHA-256 checksums to identify duplicate files.")
_ROLLBACK = _passage("Organisation SOP", "Use the rollback journal to restore applied organization moves.")
_UPLOAD = _passage("Upload Policy", "Require the file extension and MIME type to agree before upload.")
_ARCHIVE = _passage("Retention SOP", "Archive completed source files after the retention review.")
_SEARCH = _passage("Knowledge Search SOP", "Search only approved and completed knowledge sources.")

_CONFLICT_RETAIN = _passage("Retention Rule A", "Retain project invoices for seven years.", score=0.84)
_CONFLICT_REMOVE = _passage("Retention Rule B", "Delete project invoices after three years.", score=0.82)
_CONFLICT_ROUTE_A = _passage("Routing Rule A", "Send priority support requests to the supervisor queue.", score=0.84)
_CONFLICT_ROUTE_B = _passage("Routing Rule B", "Send priority support requests to the operations queue.", score=0.82)
_CONFLICT_WINDOW_A = _passage("Maintenance Rule A", "Schedule maintenance during the Sunday window.", score=0.84)
_CONFLICT_WINDOW_B = _passage("Maintenance Rule B", "Schedule maintenance during the Saturday window.", score=0.82)


EVALUATION_CASES: Final[tuple[EvaluationCase, ...]] = (
    EvaluationCase("supported-01", "supported", "How do we verify a file before restoring it?", (_RESTORE,), "answered", ("Verify file hashes before restoring a file.",)),
    EvaluationCase("supported-02", "supported", "How do we protect the original during recovery?", (_ORIGINAL,), "answered", ("Keep the original file intact during recovery.",)),
    EvaluationCase("supported-03", "supported", "Where should conflicting files be moved?", (_QUARANTINE,), "answered", ("Move conflicting files to the quarantine folder for review.",)),
    EvaluationCase("supported-04", "supported", "Which manifests are created after scanning project files?", (_INVENTORY,), "answered", ("Create JSON and CSV manifests after scanning project files.",)),
    EvaluationCase("supported-05", "supported", "When should conversion be rejected?", (_CONVERSION,), "answered", ("Reject conversion when the destination path already exists.",)),
    EvaluationCase("supported-06", "supported", "What must happen before a knowledge source is ingested?", (_APPROVAL,), "answered", ("Approve a knowledge source before it is ingested.",)),
    EvaluationCase("supported-07", "supported", "Who can retrieve project rules?", (_ACCESS,), "answered", ("Only the project owner can retrieve project rules.",)),
    EvaluationCase("supported-08", "supported", "How are duplicate files identified?", (_CHECKSUM,), "answered", ("Use SHA-256 checksums to identify duplicate files.",)),
    EvaluationCase("supported-09", "supported", "How can applied organization moves be restored?", (_ROLLBACK,), "answered", ("Use the rollback journal to restore applied organization moves.",)),
    EvaluationCase("supported-10", "supported", "What must agree before an upload?", (_UPLOAD,), "answered", ("Require the file extension and MIME type to agree before upload.",)),
    EvaluationCase("supported-11", "supported", "When are completed source files archived?", (_ARCHIVE,), "answered", ("Archive completed source files after the retention review.",)),
    EvaluationCase("supported-12", "supported", "Which knowledge sources may be searched?", (_SEARCH,), "answered", ("Search only approved and completed knowledge sources.",)),
    EvaluationCase("refusal-01", "refusal", "What is the office lunch menu?", (_RESTORE,), "refused", expected_refusal_reason="insufficient_evidence"),
    EvaluationCase("refusal-02", "refusal", "Who won the football match?", (_INVENTORY,), "refused", expected_refusal_reason="insufficient_evidence"),
    EvaluationCase("refusal-03", "refusal", "What is the weather forecast?", (_UPLOAD,), "refused", expected_refusal_reason="insufficient_evidence"),
    EvaluationCase("refusal-04", "refusal", "How do we?", (_RESTORE,), "refused", expected_refusal_reason="unsupported_query"),
    EvaluationCase("refusal-05", "refusal", "What is the company share price?", (_APPROVAL,), "refused", expected_refusal_reason="insufficient_evidence"),
    EvaluationCase("conflict-01", "conflict", "How long should project invoices be retained?", (_CONFLICT_RETAIN, _CONFLICT_REMOVE), "answered", ("Retain project invoices for seven years.", "Delete project invoices after three years.")),
    EvaluationCase("conflict-02", "conflict", "Which queue receives priority support requests?", (_CONFLICT_ROUTE_A, _CONFLICT_ROUTE_B), "answered", ("Send priority support requests to the supervisor queue.", "Send priority support requests to the operations queue.")),
    EvaluationCase("conflict-03", "conflict", "Which maintenance window should be scheduled?", (_CONFLICT_WINDOW_A, _CONFLICT_WINDOW_B), "answered", ("Schedule maintenance during the Sunday window.", "Schedule maintenance during the Saturday window.")),
)


def _result_for(case: EvaluationCase, passage: EvaluationPassage, index: int) -> SemanticSearchResult:
    seed = f"https://ccl-suite.local/evaluation/{case.case_id}/{index}"
    identifier = uuid5(NAMESPACE_URL, seed)
    return SemanticSearchResult(
        chunk_id=identifier,
        project_id=uuid5(NAMESPACE_URL, f"{seed}/project"),
        source_id=uuid5(NAMESPACE_URL, f"{seed}/source"),
        score=passage.score,
        title=passage.title,
        heading=passage.heading,
        location=f"evaluation/{case.case_id}-{index}.md#L1-L3",
        line_start=1,
        line_end=3,
        content=passage.content,
        source_type=passage.source_type,
        sensitivity=passage.sensitivity,
        file_name=f"{case.case_id}-{index}.md",
        file_storage_key=f"evaluation/{case.case_id}-{index}.md",
    )


def evaluate_case(case: EvaluationCase) -> EvaluationResult:
    """Run one fixed scenario and compare it with the evidence contract."""

    answer = compose_grounded_answer(
        case.question,
        [_result_for(case, passage, index) for index, passage in enumerate(case.passages, start=1)],
    )
    excerpts = tuple(citation.excerpt for citation in answer.citations)
    if answer.status != case.expected_status:
        return EvaluationResult(case, answer, False, f"Expected {case.expected_status}, got {answer.status}.")
    if answer.refusal_reason != case.expected_refusal_reason:
        return EvaluationResult(case, answer, False, "Refusal reason did not match the fixed contract.")
    if excerpts != case.expected_excerpts:
        return EvaluationResult(case, answer, False, "Citation excerpts did not match the fixed evidence contract.")
    return EvaluationResult(case, answer, True, None)


def run_evaluation() -> tuple[EvaluationResult, ...]:
    """Run the complete fixed suite in its stable declared order."""

    return tuple(evaluate_case(case) for case in EVALUATION_CASES)


def evaluation_counts(results: tuple[EvaluationResult, ...]) -> dict[str, int]:
    """Return compact, report-friendly counts without retaining source content."""

    return {
        "total": len(results),
        "passed": sum(result.passed for result in results),
        "failed": sum(not result.passed for result in results),
        "supported": sum(result.case.category == "supported" for result in results),
        "refusal": sum(result.case.category == "refusal" for result in results),
        "conflict": sum(result.case.category == "conflict" for result in results),
    }


__all__ = [
    "EVALUATION_CASES",
    "EvaluationCase",
    "EvaluationPassage",
    "EvaluationResult",
    "evaluate_case",
    "evaluation_counts",
    "run_evaluation",
]
