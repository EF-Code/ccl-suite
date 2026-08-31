"""Shared knowledge-source policy and approved-source query helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select

from models import File, KnowledgeSource

KNOWLEDGE_SOURCE_TYPES: tuple[str, ...] = (
    "sop",
    "prompt_bank",
    "style_guide",
    "project_rule",
)
KNOWLEDGE_SENSITIVITIES: tuple[str, ...] = (
    "public",
    "internal",
    "confidential",
    "restricted",
)
KNOWLEDGE_APPROVAL_STATUSES: tuple[str, ...] = (
    "pending",
    "approved",
    "rejected",
)


def build_approved_knowledge_sources_statement(
    project_id: UUID,
) -> Select[tuple[KnowledgeSource]]:
    """Return the only source set eligible for future knowledge-base use.

    Keeping this filter in one helper gives the Tuesday ingestion work a
    single fail-closed query to reuse.  A source must be approved and its
    referenced file must still be active; registration alone is insufficient.
    """

    return (
        select(KnowledgeSource)
        .join(File, File.id == KnowledgeSource.file_id)
        .where(
            KnowledgeSource.project_id == project_id,
            File.project_id == KnowledgeSource.project_id,
            KnowledgeSource.approval_status == "approved",
            File.status == "active",
        )
        .order_by(KnowledgeSource.created_at, KnowledgeSource.id)
    )


__all__ = [
    "KNOWLEDGE_APPROVAL_STATUSES",
    "KNOWLEDGE_SENSITIVITIES",
    "KNOWLEDGE_SOURCE_TYPES",
    "build_approved_knowledge_sources_statement",
]
