from uuid import UUID, uuid4

from api_schemas import SemanticSearchResult
from knowledge_answer import compose_grounded_answer


def passage(
    content: str,
    *,
    score: float,
    title: str = "Restore SOP",
    source_id: UUID | None = None,
) -> SemanticSearchResult:
    """Build a source-linked retrieval result for answer-composer tests."""

    return SemanticSearchResult(
        chunk_id=uuid4(),
        project_id=uuid4(),
        source_id=source_id or uuid4(),
        score=score,
        title=title,
        heading="Integrity",
        location="incoming/rules.md#L1-L4",
        line_start=1,
        line_end=4,
        content=content,
        source_type="sop",
        sensitivity="internal",
        file_name="rules.md",
        file_storage_key="incoming/rules.md",
    )


def test_composer_returns_answer_with_numbered_source_excerpt() -> None:
    result = compose_grounded_answer(
        "How do we verify a file before restoring it?",
        [
            passage(
                "# Restore\n\nVerify file hashes before restoring a file. "
                "Keep the original intact.",
                score=0.67,
            )
        ],
    )

    assert result.status == "answered"
    assert result.refusal_reason is None
    assert result.answer.startswith("Approved source evidence indicates:\n[1]")
    assert len(result.citations) == 1
    assert result.citations[0].excerpt == "Verify file hashes before restoring a file."


def test_composer_refuses_unmatched_or_low_confidence_evidence() -> None:
    result = compose_grounded_answer(
        "What is the office lunch menu?",
        [
            passage(
                "Verify file hashes before restoring a file.",
                score=0.67,
            ),
            passage(
                "Use concise plain language in every response.",
                score=0.18,
                title="Writing Style Guide",
            ),
        ],
    )

    assert result.status == "refused"
    assert result.refusal_reason == "insufficient_evidence"
    assert result.citations == ()
    assert "enough approved evidence" in result.answer


def test_composer_refuses_queries_without_meaningful_terms() -> None:
    result = compose_grounded_answer(
        "How do we?",
        [passage("Verify file hashes before restoring a file.", score=0.99)],
    )

    assert result.status == "refused"
    assert result.refusal_reason == "unsupported_query"
    assert result.citations == ()
