"""Bounded, deterministic local embeddings for the semantic-search MVP.

The project deliberately keeps this first retrieval implementation free of an
external model or vector-service dependency.  It uses a stable hashed feature
space so the same source produces the same vector in tests, on a developer
machine, and in the Compose image.  The embedding interface is isolated here
so a reviewed model provider can replace it later without changing the
project, source, or retrieval boundary.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections.abc import Sequence
from typing import Final


EMBEDDING_MODEL: Final = "local-hash-v1"
EMBEDDING_DIMENSIONS: Final = 256
MIN_SEARCH_SCORE: Final = 0.10
MAX_EMBEDDING_TEXT_CHARACTERS: Final = 32_000
_CHAR_NGRAM_SIZE: Final = 3
_CHAR_NGRAM_WEIGHT: Final = 0.25
_TOKEN_PATTERN: Final = re.compile(r"[^\W_]+(?:['’/-][^\W_]+)*", re.UNICODE)


class EmbeddingError(ValueError):
    """Raised when text or a stored vector cannot be indexed safely."""


def _normalise_text(text: str) -> str:
    """Apply stable Unicode and case normalisation before feature extraction."""

    if not isinstance(text, str):
        raise EmbeddingError("Embedding input must be text.")
    normalised = unicodedata.normalize("NFKC", text).casefold()
    if len(normalised) > MAX_EMBEDDING_TEXT_CHARACTERS:
        raise EmbeddingError("Embedding input exceeds the maximum size.")
    return normalised


def _tokens(text: str) -> tuple[str, ...]:
    """Return bounded word-like features from normalised text."""

    return tuple(_TOKEN_PATTERN.findall(_normalise_text(text)))


def _feature_bucket(feature: str) -> int:
    """Map a feature to a stable bucket without Python hash randomisation."""

    digest = hashlib.sha256(feature.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % EMBEDDING_DIMENSIONS


def _add_token_features(vector: list[float], tokens: Sequence[str]) -> None:
    """Add exact-token and character-ngram features to a vector."""

    for token in tokens:
        vector[_feature_bucket(f"token:{token}")] += 1.0
        padded = f"^{token}$"
        if len(padded) < _CHAR_NGRAM_SIZE:
            continue
        for offset in range(len(padded) - _CHAR_NGRAM_SIZE + 1):
            ngram = padded[offset : offset + _CHAR_NGRAM_SIZE]
            vector[_feature_bucket(f"char:{ngram}")] += _CHAR_NGRAM_WEIGHT


def embed_text(text: str) -> tuple[float, ...]:
    """Create a normalised, deterministic vector for one bounded text value."""

    tokens = _tokens(text)
    if not tokens:
        raise EmbeddingError("Embedding input contains no indexable terms.")

    vector = [0.0] * EMBEDDING_DIMENSIONS
    _add_token_features(vector, tokens)
    norm = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(norm) or norm <= 0.0:
        raise EmbeddingError("Embedding input could not be normalised.")
    return tuple(value / norm for value in vector)


def search_terms(text: str) -> tuple[str, ...]:
    """Return the normalised terms used by the local retrieval vocabulary."""

    return _tokens(text)


def build_chunk_embedding_text(
    title: str,
    heading: str | None,
    content: str,
) -> str:
    """Combine searchable chunk metadata and content without changing storage."""

    return "\n".join(part for part in (title, heading or "", content) if part)


def validate_embedding(vector: object) -> tuple[float, ...]:
    """Validate a JSON-decoded vector before it participates in ranking."""

    if isinstance(vector, (str, bytes, bytearray)) or not isinstance(vector, Sequence):
        raise EmbeddingError("Stored embedding has an invalid shape.")
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise EmbeddingError("Stored embedding has an invalid dimension.")

    values: list[float] = []
    for value in vector:
        if isinstance(value, bool):
            raise EmbeddingError("Stored embedding contains an invalid value.")
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise EmbeddingError("Stored embedding contains an invalid value.") from exc
        if not math.isfinite(numeric_value) or numeric_value < 0.0:
            raise EmbeddingError("Stored embedding contains an invalid value.")
        values.append(numeric_value)
    if not any(values):
        raise EmbeddingError("Stored embedding cannot be the zero vector.")
    return tuple(values)


def cosine_similarity(
    left: Sequence[float],
    right: Sequence[float],
) -> float:
    """Return a safe similarity score in the inclusive range ``0.0`` to ``1.0``."""

    left_values = validate_embedding(left)
    right_values = validate_embedding(right)
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    score = sum(
        left_value * right_value
        for left_value, right_value in zip(left_values, right_values)
    )
    score /= left_norm * right_norm
    return max(0.0, min(1.0, score))


__all__ = [
    "EMBEDDING_DIMENSIONS",
    "EMBEDDING_MODEL",
    "EmbeddingError",
    "MIN_SEARCH_SCORE",
    "MAX_EMBEDDING_TEXT_CHARACTERS",
    "build_chunk_embedding_text",
    "cosine_similarity",
    "embed_text",
    "search_terms",
    "validate_embedding",
]
