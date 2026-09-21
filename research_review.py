"""Human review state and bounded export helpers for research evidence."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable
from datetime import date, datetime
from typing import Final, Literal

from models import ResearchReview, ResearchReviewClaim


ReviewStatus = Literal[
    "needs_review",
    "changes_requested",
    "verified",
    "approved",
]
ReviewClaimStatus = Literal["needs_review", "changes_requested", "verified"]
ExportFormat = Literal["csv", "json", "markdown"]

REVIEW_STATUSES: Final[tuple[ReviewStatus, ...]] = (
    "needs_review",
    "changes_requested",
    "verified",
    "approved",
)


def effective_claim(claim: ResearchReviewClaim) -> str:
    """Return the proposed correction when one exists, otherwise the source claim."""

    return claim.corrected_claim or claim.claim


def effective_scope(claim: ResearchReviewClaim) -> dict:
    """Return the proposed scope correction when one exists."""

    return claim.corrected_scope or claim.scope


def review_status_after_claim_change(claims: Iterable[ResearchReviewClaim]) -> ReviewStatus:
    """Derive the package status from its current claim states."""

    claim_list = list(claims)
    if claim_list and all(claim.status == "verified" for claim in claim_list):
        return "verified"
    if any(claim.status == "changes_requested" for claim in claim_list):
        return "changes_requested"
    return "needs_review"


def _json_value(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _claim_payload(claim: ResearchReviewClaim) -> dict[str, object]:
    """Build one export-safe claim payload without ORM-specific values."""

    return {
        "claim_id": str(claim.claim_id),
        "status": claim.status,
        "classification": claim.classification,
        "claim": effective_claim(claim),
        "original_claim": claim.claim,
        "corrected_claim": claim.corrected_claim,
        "source_title": claim.source_title,
        "source_reference": claim.source_reference,
        "source_date": claim.source_date.isoformat() if claim.source_date else None,
        "passage": claim.passage,
        "scope": _json_value(effective_scope(claim)),
        "original_scope": _json_value(claim.scope),
        "corrected_scope": _json_value(claim.corrected_scope),
        "correction_note": claim.correction_note,
        "verified_by_id": str(claim.verified_by_id) if claim.verified_by_id else None,
        "verified_at": claim.verified_at.isoformat() if claim.verified_at else None,
    }


def review_export_payload(review: ResearchReview) -> dict[str, object]:
    """Return a JSON-serialisable representation of an approved review."""

    return {
        "schema_version": "research-review-v1",
        "review_id": str(review.id),
        "project_id": str(review.project_id),
        "status": review.status,
        "source_title": review.source_title,
        "source_reference": review.source_reference,
        "source_date": review.source_date.isoformat() if review.source_date else None,
        "target_scope": _json_value(review.target_scope),
        "approved_by_id": str(review.approved_by_id) if review.approved_by_id else None,
        "approved_at": review.approved_at.isoformat() if review.approved_at else None,
        "claims": [_claim_payload(claim) for claim in review.claims],
        "events": [
            {
                "id": str(event.id),
                "claim_id": str(event.claim_id) if event.claim_id else None,
                "actor_id": str(event.actor_id) if event.actor_id else None,
                "action": event.action,
                "note": event.note,
                "created_at": event.created_at.isoformat(),
            }
            for event in sorted(
                review.events,
                key=lambda item: (item.created_at.isoformat(), str(item.id)),
            )
        ],
    }


def _csv_cell(value: object) -> str:
    """Convert a value to a spreadsheet-safe CSV cell."""

    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _scope_cell(scope: object, field: str) -> object:
    return scope.get(field) if isinstance(scope, dict) else None


def render_csv(review: ResearchReview) -> str:
    """Render one row per reviewed claim with source provenance intact."""

    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "review_id",
            "project_id",
            "review_status",
            "claim_id",
            "claim_status",
            "classification",
            "claim",
            "original_claim",
            "corrected_claim",
            "source_title",
            "source_reference",
            "source_date",
            "passage",
            "model_year",
            "engine",
            "market",
            "population",
            "setting",
            "evidence_type",
            "correction_note",
            "verified_by_id",
            "verified_at",
        ],
    )
    writer.writeheader()
    for claim in sorted(
        review.claims,
        key=lambda item: (item.created_at.isoformat(), str(item.id)),
    ):
        scope = effective_scope(claim)
        writer.writerow(
            {
                "review_id": _csv_cell(review.id),
                "project_id": _csv_cell(review.project_id),
                "review_status": _csv_cell(review.status),
                "claim_id": _csv_cell(claim.claim_id),
                "claim_status": _csv_cell(claim.status),
                "classification": _csv_cell(claim.classification),
                "claim": _csv_cell(effective_claim(claim)),
                "original_claim": _csv_cell(claim.claim),
                "corrected_claim": _csv_cell(claim.corrected_claim),
                "source_title": _csv_cell(claim.source_title),
                "source_reference": _csv_cell(claim.source_reference),
                "source_date": _csv_cell(claim.source_date),
                "passage": _csv_cell(claim.passage),
                "model_year": _csv_cell(_scope_cell(scope, "model_year")),
                "engine": _csv_cell(_scope_cell(scope, "engine")),
                "market": _csv_cell(_scope_cell(scope, "market")),
                "population": _csv_cell(_scope_cell(scope, "population")),
                "setting": _csv_cell(_scope_cell(scope, "setting")),
                "evidence_type": _csv_cell(_scope_cell(scope, "evidence_type")),
                "correction_note": _csv_cell(claim.correction_note),
                "verified_by_id": _csv_cell(claim.verified_by_id),
                "verified_at": _csv_cell(claim.verified_at),
            }
        )
    return output.getvalue()


def render_markdown(review: ResearchReview) -> str:
    """Render a readable publication copy for human consumers."""

    lines = [
        "# Research evidence review",
        "",
        f"- Review: `{review.id}`",
        f"- Project: `{review.project_id}`",
        f"- Status: **{review.status}**",
        f"- Source: {review.source_title} ({review.source_reference})",
        f"- Source date: {review.source_date.isoformat() if review.source_date else 'Not supplied'}",
        "",
        "## Claims",
        "",
    ]
    for index, claim in enumerate(
        sorted(
            review.claims,
            key=lambda item: (item.created_at.isoformat(), str(item.id)),
        ),
        start=1,
    ):
        text = effective_claim(claim).replace("|", "\\|").replace("\n", " ")
        passage = claim.passage.replace("|", "\\|").replace("\n", " ")
        lines.extend(
            [
                f"### {index}. {claim.classification.title()} · {claim.status}",
                "",
                f"**Claim:** {text}",
                "",
                f"**Source passage:** {passage}",
                "",
                f"**Source reference:** `{claim.source_reference}`",
                "",
            ]
        )
        if claim.correction_note:
            lines.extend([f"**Correction note:** {claim.correction_note}", ""])
    return "\n".join(lines)


def render_export(review: ResearchReview, export_format: ExportFormat) -> tuple[str, str]:
    """Return rendered content and its response media type."""

    if export_format == "csv":
        return render_csv(review), "text/csv; charset=utf-8"
    if export_format == "markdown":
        return render_markdown(review), "text/markdown; charset=utf-8"
    return (
        json.dumps(review_export_payload(review), ensure_ascii=False, indent=2, sort_keys=True),
        "application/json",
    )


__all__ = [
    "ExportFormat",
    "REVIEW_STATUSES",
    "ReviewClaimStatus",
    "ReviewStatus",
    "effective_claim",
    "effective_scope",
    "render_export",
    "review_export_payload",
    "review_status_after_claim_change",
]
