"""Safely archive and restore immutable file-version snapshots."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from file_inventory import resolve_approved_root, safe_relative_path, sha256_file
from models import FileVersion

VERSION_ARCHIVE_DIRECTORY = ".ccl-versions"


class RestoreError(ValueError):
    """Base error for a restore operation that fails its safety checks."""


class RestoreSourceUnavailableError(RestoreError):
    """Raised when an immutable archived version is missing or was altered."""


class RestoreDestinationExistsError(RestoreError):
    """Raised instead of replacing an existing destination file."""


class UnsafeRestorePathError(RestoreError):
    """Raised when a restore path leaves the approved project root."""


@dataclass(frozen=True)
class RestoreResult:
    """Details about one safely restored version copy."""

    root: Path
    destination: Path
    version_number: int
    checksum_sha256: str
    bytes_restored: int

    @property
    def destination_relative(self) -> Path:
        """Return the destination path relative to the approved root."""

        return safe_relative_path(self.root, self.destination)


def version_archive_path(
    approved_root: Path | str,
    file_id: UUID,
    version_number: int,
) -> Path:
    """Return the private, deterministic archive path for one version."""

    if version_number < 1:
        raise ValueError("Version number must be positive.")
    root = resolve_approved_root(approved_root)
    return root / VERSION_ARCHIVE_DIRECTORY / str(file_id) / str(version_number)


def _source_path(root: Path, storage_key: str, label: str) -> Path:
    """Resolve a regular, non-symlink source below the approved root."""

    candidate = root / storage_key
    if candidate.is_symlink():
        raise RestoreSourceUnavailableError(f"{label} must not be a symlink.")
    resolved = candidate.resolve(strict=False)
    try:
        safe_relative_path(root, resolved)
    except ValueError as exc:
        raise UnsafeRestorePathError(f"{label} must remain inside the approved root.") from exc
    if not resolved.is_file():
        raise RestoreSourceUnavailableError(f"{label} is not available.")
    return resolved


def _destination_path(root: Path, destination: Path | str) -> Path:
    """Resolve a new destination below the approved root."""

    candidate = Path(destination)
    if candidate.is_absolute():
        raise UnsafeRestorePathError("Restore destination must be a relative path.")
    path = root / candidate
    if path.is_symlink():
        raise UnsafeRestorePathError("Restore destination must not be a symlink.")
    resolved = path.resolve(strict=False)
    try:
        safe_relative_path(root, resolved)
    except ValueError as exc:
        raise UnsafeRestorePathError(
            "Restore destination must remain inside the approved project root."
        ) from exc
    if resolved.exists():
        raise RestoreDestinationExistsError(
            "Restore destination already exists and will not be overwritten."
        )
    return resolved


def _validate_version_archive(root: Path, version: FileVersion) -> Path:
    """Locate and verify the archived bytes for a version."""

    archive = version_archive_path(root, version.file_id, version.version_number)
    if archive.is_symlink() or not archive.is_file():
        raise RestoreSourceUnavailableError("The requested version archive is unavailable.")
    if archive.stat().st_size != version.size_bytes:
        raise RestoreSourceUnavailableError("The requested version archive is incomplete.")
    if sha256_file(archive) != version.checksum_sha256:
        raise RestoreSourceUnavailableError("The requested version archive failed checksum verification.")
    return archive


def _copy_without_overwrite(source: Path, destination: Path) -> int:
    """Copy bytes through a temporary file and atomically link the destination."""

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    temporary_path: Path | None = None
    try:
        with source.open("rb") as source_stream:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination.parent,
                prefix=".restore-",
                delete=False,
            ) as destination_stream:
                temporary_path = Path(destination_stream.name)
                shutil.copyfileobj(source_stream, destination_stream)
                destination_stream.flush()
                os.fsync(destination_stream.fileno())
        try:
            os.link(temporary_path, destination)
        except FileExistsError as exc:
            raise RestoreDestinationExistsError(
                "Restore destination already exists and will not be overwritten."
            ) from exc
        return destination.stat().st_size
    except OSError as exc:
        if isinstance(exc, RestoreError):
            raise
        raise RestoreError("Restored file could not be written safely.") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def archive_version_content(approved_root: Path | str, version: FileVersion) -> Path:
    """Archive the current file bytes for a newly-created immutable version."""

    root = resolve_approved_root(approved_root)
    source = _source_path(root, version.storage_key, "Version source")
    if source.stat().st_size != version.size_bytes or sha256_file(source) != version.checksum_sha256:
        raise RestoreSourceUnavailableError("Version source metadata does not match its content.")

    destination = version_archive_path(root, version.file_id, version.version_number)
    if destination.exists():
        if destination.is_file() and destination.stat().st_size == version.size_bytes:
            if sha256_file(destination) == version.checksum_sha256:
                return destination
        raise RestoreError("An existing version archive does not match the requested version.")
    _copy_without_overwrite(source, destination)
    return destination


def restore_version_content(
    approved_root: Path | str,
    version: FileVersion,
    destination: Path | str,
) -> RestoreResult:
    """Restore archived bytes to a new path without replacing the original."""

    root = resolve_approved_root(approved_root)
    archive = _validate_version_archive(root, version)
    original_path = (root / version.storage_key).resolve(strict=False)
    candidate = Path(destination)
    if not candidate.is_absolute() and (root / candidate).resolve(strict=False) == original_path:
        raise UnsafeRestorePathError(
            "Restore destination must differ from the original file path."
        )
    destination_path = _destination_path(root, destination)
    if destination_path == original_path:
        raise UnsafeRestorePathError(
            "Restore destination must differ from the original file path."
        )
    bytes_restored = _copy_without_overwrite(archive, destination_path)
    return RestoreResult(
        root=root,
        destination=destination_path,
        version_number=version.version_number,
        checksum_sha256=version.checksum_sha256,
        bytes_restored=bytes_restored,
    )


__all__ = [
    "RestoreDestinationExistsError",
    "RestoreError",
    "RestoreResult",
    "RestoreSourceUnavailableError",
    "UnsafeRestorePathError",
    "VERSION_ARCHIVE_DIRECTORY",
    "archive_version_content",
    "restore_version_content",
    "version_archive_path",
]
