"""Deterministic, evidence-first answer composition for the knowledge base."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from api_schemas import SemanticSearchResult
from semantic_search import search_terms


ANSWER_ENGINE: Final = "local-extractive-v1"
MIN_ANSWER_SCORE: Final = 0.30
MAX_ANSWER_CITATIONS: Final = 3
MAX_CITATION_EXCERPT_CHARACTERS: Final = 800

_SENTENCE_BOUNDARY: Final = re.compile(r"(?<=[.!?])\s+|\n+")
_STOP_WORDS: Final = frozenset(
    {
        "a",
        "about",
        "an",
        "and",
        "are",
        "be",
        "can",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "of",
        "on",
        "or",
        "please",
        "tell",
        "that",
        "the",
        "these",
        "this",
        "those",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "you",
    }
)


@dataclass(frozen=True)
class GroundedCitation:
    """One source-linked excerpt supporting a composed answer."""

    chunk_id: UUID
    source_id: UUID
    score: float
    title: str
    heading: str | None
    location: str
    line_start: int
    line_end: int
    file_name: str
    file_storage_key: str
    excerpt: str


@dataclass(frozen=True)
class GroundedAnswer:
    """A safe answer or a refusal when retrieved evidence is insufficient."""

    status: Literal["answered", "refused"]
    answer: str
    refusal_reason: Literal["unsupported_query", "insufficient_evidence"] | None
    citations: tuple[GroundedCitation, ...]


def _meaningful_terms(query: str) -> frozenset[str]:
    """Remove conversational filler before comparing question and evidence."""

    return frozenset(term for term in search_terms(query) if term not in _STOP_WORDS)


def _best_excerpt(content: str, terms: frozenset[str]) -> tuple[str, int]:
    """Select the shortest high-overlap sentence from one retrieved passage."""

    segments = [segment.strip() for segment in _SENTENCE_BOUNDARY.split(content) if segment.strip()]
    if not segments:
        return "", 0

    scored: list[tuple[int, int, str]] = []
    for segment in segments:
        overlap = len(terms.intersection(search_terms(segment)))
        scored.append((overlap, len(segment), segment))
    overlap, _length, excerpt = max(scored, key=lambda item: (item[0], -item[1], item[2]))
    if len(excerpt) > MAX_CITATION_EXCERPT_CHARACTERS:
        excerpt = excerpt[: MAX_CITATION_EXCERPT_CHARACTERS - 1].rstrip() + "…"
    return excerpt, overlap


def compose_grounded_answer(
    query: str,
    passages: Sequence[SemanticSearchResult],
) -> GroundedAnswer:
    """Compose an answer only from passages that clear score and term checks.

    This MVP deliberately quotes bounded source excerpts instead of calling a
    model.  That makes the answer traceable and ensures unsupported questions
    produce a refusal rather than an invented policy.
    """

    terms = _meaningful_terms(query)
    if not terms:
        return GroundedAnswer(
            status="refused",
            answer="I don't have enough approved evidence to answer that question.",
            refusal_reason="unsupported_query",
            citations=(),
        )

    candidates: list[tuple[float, int, SemanticSearchResult, str]] = []
    for passage in passages:
        if passage.score < MIN_ANSWER_SCORE:
            continue
        excerpt, overlap = _best_excerpt(passage.content, terms)
        if not excerpt or overlap == 0:
            continue
        candidates.append((passage.score, overlap, passage, excerpt))

    candidates.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            item[2].location,
            item[2].chunk_id.int,
        )
    )

    selected: list[tuple[SemanticSearchResult, str]] = []
    seen_sources: set[UUID] = set()
    for _score, _overlap, passage, excerpt in candidates:
        if passage.source_id in seen_sources:
            continue
        selected.append((passage, excerpt))
        seen_sources.add(passage.source_id)
        if len(selected) >= MAX_ANSWER_CITATIONS:
            break

    if not selected:
        return GroundedAnswer(
            status="refused",
            answer="I don't have enough approved evidence to answer that question.",
            refusal_reason="insufficient_evidence",
            citations=(),
        )

    citations = tuple(
        GroundedCitation(
            chunk_id=passage.chunk_id,
            source_id=passage.source_id,
            score=passage.score,
            title=passage.title,
            heading=passage.heading,
            location=passage.location,
            line_start=passage.line_start,
            line_end=passage.line_end,
            file_name=passage.file_name,
            file_storage_key=passage.file_storage_key,
            excerpt=excerpt,
        )
        for passage, excerpt in selected
    )
    answer = "Approved source evidence indicates:\n" + "\n".join(
        f"[{number}] {citation.excerpt}"
        for number, citation in enumerate(citations, start=1)
    )
    return GroundedAnswer(
        status="answered",
        answer=answer,
        refusal_reason=None,
        citations=citations,
    )


__all__ = [
    "ANSWER_ENGINE",
    "MAX_ANSWER_CITATIONS",
    "MAX_CITATION_EXCERPT_CHARACTERS",
    "MIN_ANSWER_SCORE",
    "GroundedAnswer",
    "GroundedCitation",
    "compose_grounded_answer",
]
