import pytest

from semantic_search import (
    EMBEDDING_DIMENSIONS,
    EmbeddingError,
    build_chunk_embedding_text,
    cosine_similarity,
    embed_text,
    validate_embedding,
)


def test_embedding_is_deterministic_and_normalised() -> None:
    text = "Verify file hashes before restoring a project file."

    first = embed_text(text)
    second = embed_text(text)

    assert first == second
    assert len(first) == EMBEDDING_DIMENSIONS
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_matching_passage_scores_above_unrelated_passage() -> None:
    query = embed_text("verify hashes before restoring files")
    matching = embed_text(
        build_chunk_embedding_text(
            "Restore procedure",
            "Integrity",
            "Verify file hashes before restoring a file.",
        )
    )
    unrelated = embed_text("The style guide prefers concise plain language.")

    assert cosine_similarity(query, matching) > cosine_similarity(query, unrelated)
    assert 0.0 < cosine_similarity(query, matching) <= 1.0


def test_embedding_rejects_empty_and_malformed_values() -> None:
    with pytest.raises(EmbeddingError):
        embed_text("... ---")
    with pytest.raises(EmbeddingError):
        validate_embedding([0.0] * EMBEDDING_DIMENSIONS)
    with pytest.raises(EmbeddingError):
        validate_embedding([1.0, 2.0])
