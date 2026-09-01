from pathlib import Path

import pytest

from document_ingestion import (
    DEFAULT_CHUNK_CHARACTERS,
    DocumentChunkConfigError,
    DocumentSourceError,
    UnsupportedDocumentError,
    chunk_text,
    normalize_document_type,
    read_document,
)


def test_normalize_document_type_accepts_allowlisted_text_files() -> None:
    assert normalize_document_type("incoming/rules.md", "text/markdown; charset=utf-8") == (
        ".md",
        "text/markdown",
    )
    assert normalize_document_type("incoming/rows.csv", "application/csv") == (
        ".csv",
        "application/csv",
    )


def test_normalize_document_type_rejects_unsafe_or_binary_types() -> None:
    with pytest.raises(UnsupportedDocumentError, match="Only .txt"):
        normalize_document_type("incoming/guide.pdf", "application/pdf")
    with pytest.raises(UnsupportedDocumentError, match="does not match"):
        normalize_document_type("incoming/guide.md", "application/octet-stream")
    with pytest.raises(UnsupportedDocumentError, match="approved project root"):
        normalize_document_type("../guide.md", "text/markdown")


def test_read_document_normalizes_utf8_bom_and_line_endings(tmp_path: Path) -> None:
    path = tmp_path / "rules.md"
    payload = "\ufeff# Rules\r\n\r\nKeep originals.\r"
    path.write_bytes(payload.encode("utf-8"))

    document = read_document(
        path,
        storage_key="incoming/rules.md",
        media_type="text/markdown",
    )

    assert document.text == "# Rules\n\nKeep originals.\n"
    assert document.size_bytes == len(payload.encode("utf-8"))
    assert len(document.checksum_sha256) == 64


def test_read_document_rejects_empty_binary_and_oversized_sources(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("\n\t", encoding="utf-8")
    with pytest.raises(DocumentSourceError, match="no extractable"):
        read_document(empty, storage_key="incoming/empty.txt", media_type="text/plain")

    binary = tmp_path / "binary.txt"
    binary.write_bytes(b"valid\x00binary")
    with pytest.raises(DocumentSourceError, match="binary"):
        read_document(binary, storage_key="incoming/binary.txt", media_type="text/plain")

    oversized = tmp_path / "large.txt"
    oversized.write_bytes(b"x" * 11)
    with pytest.raises(DocumentSourceError, match="maximum"):
        read_document(
            oversized,
            storage_key="incoming/large.txt",
            media_type="text/plain",
            max_bytes=10,
        )


def test_chunk_text_preserves_markdown_heading_and_source_location() -> None:
    text = "# Access\n\nKeep originals.\nUse approved folders.\n\n## Restore\n\nVerify hashes."

    chunks = chunk_text(
        text,
        storage_key="incoming/rules.md",
        max_characters=42,
        overlap_characters=8,
    )

    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert chunks[0].heading == "Access"
    assert chunks[-1].heading == "Restore"
    assert chunks[0].location.startswith("incoming/rules.md#L")
    assert all(chunk.character_count == len(chunk.content) for chunk in chunks)
    assert all(len(chunk.checksum_sha256) == 64 for chunk in chunks)


def test_chunk_text_is_deterministic_and_applies_overlap() -> None:
    text = " ".join(f"word-{index}" for index in range(80))
    first = chunk_text(
        text,
        storage_key="incoming/notes.txt",
        max_characters=DEFAULT_CHUNK_CHARACTERS // 6,
        overlap_characters=10,
    )
    second = chunk_text(
        text,
        storage_key="incoming/notes.txt",
        max_characters=DEFAULT_CHUNK_CHARACTERS // 6,
        overlap_characters=10,
    )

    assert first == second
    assert len(first) > 1
    assert any(left.content[-5:] in right.content for left, right in zip(first, first[1:]))


def test_chunk_text_rejects_invalid_configuration() -> None:
    with pytest.raises(DocumentChunkConfigError, match="positive"):
        chunk_text("content", storage_key="incoming/a.txt", max_characters=0)
    with pytest.raises(DocumentChunkConfigError, match="smaller"):
        chunk_text("content", storage_key="incoming/a.txt", max_characters=10, overlap_characters=10)
