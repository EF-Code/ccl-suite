"""Safe text extraction and deterministic chunking for approved documents."""

from __future__ import annotations

import hashlib
import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

from file_records import validate_storage_key


MAX_DOCUMENT_BYTES = 1_048_576
DEFAULT_CHUNK_CHARACTERS = 1_200
DEFAULT_CHUNK_OVERLAP = 120

SUPPORTED_DOCUMENT_MEDIA_TYPES: dict[str, frozenset[str]] = {
    ".txt": frozenset({"text/plain"}),
    ".md": frozenset({"text/markdown", "text/plain"}),
    ".csv": frozenset({"text/csv", "application/csv"}),
    ".json": frozenset({"application/json"}),
}

MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


class DocumentProcessingError(ValueError):
    """Base error for a document that cannot be processed safely."""


class UnsupportedDocumentError(DocumentProcessingError):
    """Raised when the file extension or media type is not allow-listed."""


class DocumentSourceError(DocumentProcessingError):
    """Raised when the source cannot be read as bounded UTF-8 text."""


class DocumentChunkConfigError(DocumentProcessingError):
    """Raised when chunk size or overlap settings are unsafe."""


@dataclass(frozen=True)
class ExtractedDocument:
    """The bounded text and integrity metadata read from one source file."""

    text: str
    extension: str
    media_type: str
    size_bytes: int
    checksum_sha256: str


@dataclass(frozen=True)
class ChunkDraft:
    """One deterministic chunk before it is associated with database records."""

    chunk_index: int
    content: str
    heading: str | None
    location: str
    line_start: int
    line_end: int
    character_count: int
    word_count: int
    checksum_sha256: str


def normalize_document_type(storage_key: str, media_type: str) -> tuple[str, str]:
    """Validate a project-relative text document type and normalize its values."""

    try:
        normalized_key = validate_storage_key(storage_key)
    except ValueError as exc:
        raise UnsupportedDocumentError(str(exc)) from exc

    extension = Path(normalized_key).suffix.lower()
    normalized_media_type = (media_type or "").split(";", 1)[0].strip().lower()
    allowed_media_types = SUPPORTED_DOCUMENT_MEDIA_TYPES.get(extension)
    if not allowed_media_types:
        raise UnsupportedDocumentError(
            "Only .txt, .md, .csv, and .json documents can be ingested."
        )
    if normalized_media_type not in allowed_media_types:
        raise UnsupportedDocumentError(
            "Document MIME type does not match its supported text extension."
        )
    return extension, normalized_media_type


def read_document(
    path: Path,
    *,
    storage_key: str,
    media_type: str,
    max_bytes: int = MAX_DOCUMENT_BYTES,
) -> ExtractedDocument:
    """Read one allow-listed source with a size and text-integrity boundary."""

    extension, normalized_media_type = normalize_document_type(storage_key, media_type)
    if max_bytes <= 0:
        raise DocumentSourceError("Document size limit must be positive.")
    if path.is_symlink() or not path.is_file():
        raise DocumentSourceError("Document source is not a regular file.")

    try:
        with path.open("rb") as stream:
            payload = stream.read(max_bytes + 1)
    except OSError as exc:
        raise DocumentSourceError("Document source could not be read.") from exc

    if len(payload) > max_bytes:
        raise DocumentSourceError("Document exceeds the maximum ingestion size.")
    if not payload:
        raise DocumentSourceError("Document contains no extractable text.")

    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentSourceError("Document must contain valid UTF-8 text.") from exc
    if "\x00" in text:
        raise DocumentSourceError("Document contains binary data and cannot be ingested.")

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized_text.strip():
        raise DocumentSourceError("Document contains no extractable text.")

    return ExtractedDocument(
        text=normalized_text,
        extension=extension,
        media_type=normalized_media_type,
        size_bytes=len(payload),
        checksum_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _heading_for_line(line: str) -> str | None:
    """Return a normalized Markdown heading, if one is present."""

    match = MARKDOWN_HEADING.match(line)
    if not match:
        return None
    heading = " ".join(match.group(1).split())
    return heading or None


def _heading_positions(text: str) -> tuple[list[int], list[str | None]]:
    """Build a compact index of the active heading at each line start."""

    positions: list[int] = []
    headings: list[str | None] = []
    current_heading: str | None = None
    position = 0
    for line in text.splitlines(keepends=True):
        positions.append(position)
        heading = _heading_for_line(line.rstrip("\n"))
        if heading is not None:
            current_heading = heading
        headings.append(current_heading)
        position += len(line)
    if not positions:
        positions.append(0)
        headings.append(None)
    return positions, headings


def _line_number(text: str, character_index: int) -> int:
    """Return the one-based source line containing a character offset."""

    return text.count("\n", 0, character_index) + 1


def chunk_text(
    text: str,
    *,
    storage_key: str,
    max_characters: int = DEFAULT_CHUNK_CHARACTERS,
    overlap_characters: int = DEFAULT_CHUNK_OVERLAP,
) -> tuple[ChunkDraft, ...]:
    """Split text into deterministic, bounded windows with source metadata.

    Chunks prefer paragraph and line boundaries.  A long single line falls
    back to a hard character boundary.  Overlap is measured on the normalized
    source text, and all chunks retain a project-relative source location.
    """

    try:
        normalized_key = validate_storage_key(storage_key)
    except ValueError as exc:
        raise DocumentChunkConfigError(str(exc)) from exc
    if max_characters <= 0:
        raise DocumentChunkConfigError("Chunk size must be positive.")
    if overlap_characters < 0 or overlap_characters >= max_characters:
        raise DocumentChunkConfigError(
            "Chunk overlap must be non-negative and smaller than chunk size."
        )

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized_text.strip():
        return ()

    line_positions, line_headings = _heading_positions(normalized_text)
    chunks: list[ChunkDraft] = []
    start = 0
    text_length = len(normalized_text)

    while start < text_length:
        raw_end = min(start + max_characters, text_length)
        end = raw_end
        if raw_end < text_length:
            boundary_start = min(start + max_characters // 2, raw_end)
            paragraph_boundary = normalized_text.rfind("\n\n", boundary_start, raw_end)
            line_boundary = normalized_text.rfind("\n", boundary_start, raw_end)
            boundary = max(paragraph_boundary, line_boundary)
            if boundary > start:
                end = boundary

        content = normalized_text[start:end].strip()
        if content:
            heading_index = max(0, bisect_right(line_positions, max(start, end - 1)) - 1)
            line_start = _line_number(normalized_text, start)
            line_end = _line_number(normalized_text, max(start, end - 1))
            chunks.append(
                ChunkDraft(
                    chunk_index=len(chunks),
                    content=content,
                    heading=line_headings[heading_index],
                    location=f"{normalized_key}#L{line_start}-L{line_end}",
                    line_start=line_start,
                    line_end=line_end,
                    character_count=len(content),
                    word_count=len(content.split()),
                    checksum_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
            )

        if end >= text_length:
            break
        next_start = end - overlap_characters
        if next_start <= start:
            next_start = end
        start = next_start

    return tuple(chunks)


__all__ = [
    "ChunkDraft",
    "DEFAULT_CHUNK_CHARACTERS",
    "DEFAULT_CHUNK_OVERLAP",
    "DocumentChunkConfigError",
    "DocumentProcessingError",
    "DocumentSourceError",
    "ExtractedDocument",
    "MAX_DOCUMENT_BYTES",
    "SUPPORTED_DOCUMENT_MEDIA_TYPES",
    "UnsupportedDocumentError",
    "chunk_text",
    "normalize_document_type",
    "read_document",
]
