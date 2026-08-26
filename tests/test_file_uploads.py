from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from file_uploads import (
    UploadDestinationExistsError,
    UploadTooLargeError,
    UploadValidationError,
    store_upload,
    validate_upload_metadata,
)


async def chunks(payload: bytes):
    for start in range(0, len(payload), 2):
        yield payload[start : start + 2]


def test_store_upload_validates_and_hashes_content(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    result = asyncio.run(
        store_upload(
            root,
            "incoming/notes.txt",
            "text/plain; charset=utf-8",
            chunks(b"hello"),
            content_length=5,
        )
    )

    assert result.destination_relative == Path("incoming/notes.txt")
    assert result.size_bytes == 5
    assert result.checksum_sha256 == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert (root / "incoming/notes.txt").read_bytes() == b"hello"


def test_store_upload_rejects_unsafe_names_and_mime_types(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    with pytest.raises(UploadValidationError):
        validate_upload_metadata("incoming/report.csv.exe", "application/octet-stream")
    with pytest.raises(UploadValidationError):
        validate_upload_metadata("../outside.txt", "text/plain")
    with pytest.raises(UploadValidationError):
        validate_upload_metadata("incoming/report.json", "text/plain")


def test_upload_metadata_accepts_allowed_mime_parameters() -> None:
    assert validate_upload_metadata(
        "incoming/report.csv", "text/csv; charset=utf-8"
    ) == ("incoming/report.csv", ".csv", "text/csv")
    assert validate_upload_metadata(
        "incoming/notes.md", "text/markdown"
    ) == ("incoming/notes.md", ".md", "text/markdown")


@pytest.mark.parametrize(
    ("storage_key", "content_type"),
    [
        ("incoming/", "text/plain"),
        ("incoming/report", "text/plain"),
        ("incoming/report.txt ", "text/plain"),
        ("incoming/report.exe", "application/octet-stream"),
    ],
)
def test_upload_metadata_rejects_invalid_names(
    storage_key: str, content_type: str
) -> None:
    with pytest.raises(UploadValidationError):
        validate_upload_metadata(storage_key, content_type)


def test_store_upload_rejects_oversized_and_existing_destinations(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    with pytest.raises(UploadTooLargeError):
        asyncio.run(
            store_upload(
                root,
                "incoming/large.txt",
                "text/plain",
                chunks(b"12345"),
                content_length=2_000_000,
            )
        )

    existing = root / "incoming" / "notes.txt"
    existing.parent.mkdir()
    existing.write_text("keep", encoding="utf-8")
    with pytest.raises(UploadDestinationExistsError):
        asyncio.run(
            store_upload(
                root,
                "incoming/notes.txt",
                "text/plain",
                chunks(b"replace"),
            )
        )
    assert existing.read_text(encoding="utf-8") == "keep"
