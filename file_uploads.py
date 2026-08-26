"""Validation and bounded storage for project-file uploads."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterable

from file_inventory import resolve_approved_root, safe_relative_path
from file_records import validate_storage_key

MAX_UPLOAD_BYTES = 1_048_576
UPLOAD_FILENAME_MAX_LENGTH = 255
UPLOAD_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ALLOWED_UPLOAD_MEDIA_TYPES: dict[str, frozenset[str]] = {
    ".csv": frozenset({"text/csv", "application/csv"}),
    ".json": frozenset({"application/json"}),
    ".md": frozenset({"text/markdown", "text/plain"}),
    ".txt": frozenset({"text/plain"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".png": frozenset({"image/png"}),
}


class UploadValidationError(ValueError):
    """Raised when an upload fails an allowlist or path check."""


class UploadDestinationExistsError(UploadValidationError):
    """Raised instead of replacing an existing destination file."""


class UploadTooLargeError(UploadValidationError):
    """Raised when an upload exceeds the configured byte limit."""


class UploadLengthMismatchError(UploadValidationError):
    """Raised when a declared content length differs from received bytes."""


class UploadWriteError(UploadValidationError):
    """Raised when validated upload bytes cannot be stored safely."""


@dataclass(frozen=True)
class UploadResult:
    """Details about one safely stored upload."""

    root: Path
    destination: Path
    storage_key: str
    name: str
    extension: str
    media_type: str
    size_bytes: int
    checksum_sha256: str
    modified_at: datetime

    @property
    def destination_relative(self) -> Path:
        """Return the destination path relative to the approved root."""

        return safe_relative_path(self.root, self.destination)


def normalize_media_type(value: str | None) -> str:
    """Normalize a request content type without accepting parameters."""

    media_type = (value or "").split(";", 1)[0].strip().lower()
    if not media_type:
        raise UploadValidationError("Upload Content-Type is required.")
    return media_type


def validate_upload_name(storage_key: str) -> tuple[str, str]:
    """Validate one project-relative filename and return name plus extension."""

    try:
        normalized_key = validate_storage_key(storage_key)
    except ValueError as exc:
        raise UploadValidationError(str(exc)) from exc
    name = Path(normalized_key).name
    if (
        not name
        or len(name) > UPLOAD_FILENAME_MAX_LENGTH
        or UPLOAD_FILENAME_PATTERN.fullmatch(name) is None
    ):
        raise UploadValidationError("Upload filename contains disallowed characters.")
    suffixes = Path(name).suffixes
    if len(suffixes) != 1:
        raise UploadValidationError("Upload filename must contain exactly one extension.")
    extension = suffixes[0].lower()
    if extension not in ALLOWED_UPLOAD_MEDIA_TYPES:
        raise UploadValidationError("Upload extension is not allowed.")
    return normalized_key, extension


def validate_upload_metadata(storage_key: str, content_type: str | None) -> tuple[str, str, str]:
    """Validate destination name and declared MIME type against allowlists."""

    normalized_key, extension = validate_upload_name(storage_key)
    media_type = normalize_media_type(content_type)
    if media_type not in ALLOWED_UPLOAD_MEDIA_TYPES[extension]:
        raise UploadValidationError("Upload MIME type does not match its extension.")
    return normalized_key, extension, media_type


def validate_content_length(content_length: int | None) -> None:
    """Validate an optional declared length before streaming the body."""

    if content_length is not None and content_length < 0:
        raise UploadValidationError("Upload Content-Length must not be negative.")
    if content_length is not None and content_length > MAX_UPLOAD_BYTES:
        raise UploadTooLargeError("Upload exceeds the maximum allowed size.")


def upload_policy() -> dict[str, object]:
    """Return the public, non-secret upload policy for clients."""

    return {
        "max_size_bytes": MAX_UPLOAD_BYTES,
        "allowed_extensions": {
            extension: sorted(media_types)
            for extension, media_types in ALLOWED_UPLOAD_MEDIA_TYPES.items()
        },
        "filename_pattern": UPLOAD_FILENAME_PATTERN.pattern,
    }


def _resolve_destination(root: Path, storage_key: str) -> Path:
    """Resolve a new, non-symlink destination below the approved root."""

    candidate = root / storage_key
    if candidate.is_symlink():
        raise UploadValidationError("Upload destination must not be a symlink.")
    resolved = candidate.resolve(strict=False)
    try:
        safe_relative_path(root, resolved)
    except ValueError as exc:
        raise UploadValidationError("Upload destination must remain inside project storage.") from exc
    if resolved.exists():
        raise UploadDestinationExistsError("Upload destination already exists.")
    return resolved


async def store_upload(
    approved_root: Path | str,
    storage_key: str,
    content_type: str | None,
    body_stream: AsyncIterable[bytes],
    *,
    content_length: int | None = None,
) -> UploadResult:
    """Validate and stream one upload without buffering it in memory."""

    normalized_key, extension, media_type = validate_upload_metadata(
        storage_key, content_type
    )
    validate_content_length(content_length)

    root = resolve_approved_root(approved_root)
    destination = _resolve_destination(root, normalized_key)
    digest = hashlib.sha256()
    size_bytes = 0
    temporary_path: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=".upload-",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            async for chunk in body_stream:
                if not isinstance(chunk, bytes):
                    raise UploadWriteError("Upload stream returned invalid data.")
                size_bytes += len(chunk)
                if size_bytes > MAX_UPLOAD_BYTES:
                    raise UploadTooLargeError("Upload exceeds the maximum allowed size.")
                digest.update(chunk)
                stream.write(chunk)
            if content_length is not None and size_bytes != content_length:
                raise UploadLengthMismatchError(
                    "Upload Content-Length does not match received bytes."
                )
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary_path, destination)
        except FileExistsError as exc:
            raise UploadDestinationExistsError("Upload destination already exists.") from exc
    except UploadValidationError:
        raise
    except OSError as exc:
        raise UploadWriteError("Upload could not be stored safely.") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return UploadResult(
        root=root,
        destination=destination,
        storage_key=normalized_key,
        name=Path(normalized_key).name,
        extension=extension,
        media_type=media_type,
        size_bytes=size_bytes,
        checksum_sha256=digest.hexdigest(),
        modified_at=datetime.now(timezone.utc),
    )


__all__ = [
    "ALLOWED_UPLOAD_MEDIA_TYPES",
    "MAX_UPLOAD_BYTES",
    "UPLOAD_FILENAME_MAX_LENGTH",
    "UploadDestinationExistsError",
    "UploadLengthMismatchError",
    "UploadResult",
    "UploadTooLargeError",
    "UploadValidationError",
    "UploadWriteError",
    "normalize_media_type",
    "store_upload",
    "upload_policy",
    "validate_content_length",
    "validate_upload_metadata",
    "validate_upload_name",
]
