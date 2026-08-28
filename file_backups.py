"""Project-level backup contracts and storage-path safety helpers.

The backup implementation keeps archives outside project storage, stores only
relative artifact keys in the database, and treats every user-controlled path
as untrusted input.  Archive creation, verification, and restoration build on
the small immutable contracts defined here.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Literal
from uuid import UUID, uuid4

from file_inventory import resolve_approved_root, sha256_file

BACKUP_FORMAT_VERSION = 1
BACKUP_ARCHIVE_SUFFIX = ".tar"
BACKUP_MANIFEST_SUFFIX = ".manifest.json"
DEFAULT_BACKUP_ROOT = Path(os.getenv("CCL_BACKUP_ROOT", "backups"))
BackupEntryKind = Literal["file", "directory"]


class BackupError(ValueError):
    """Base error for a backup operation that fails validation or I/O."""


class BackupPathError(BackupError):
    """Raised when a project, artifact, or restore path is unsafe."""


class BackupSourceError(BackupError):
    """Raised when the project source contains unsupported filesystem state."""


class BackupArtifactError(BackupError):
    """Raised when a backup artifact cannot be created or used."""


class BackupIntegrityError(BackupArtifactError):
    """Raised when an archive or manifest fails integrity validation."""


class BackupDestinationExistsError(BackupError):
    """Raised instead of replacing an existing restore destination."""


@dataclass(frozen=True)
class BackupEntry:
    """One deterministic project entry recorded in a backup manifest."""

    relative_path: str
    kind: BackupEntryKind
    size_bytes: int
    checksum_sha256: str | None
    mode: int


@dataclass(frozen=True)
class BackupManifest:
    """The versioned, JSON-serialisable description of one project backup."""

    format_version: int
    project_ref: str
    entries: tuple[BackupEntry, ...]


@dataclass(frozen=True)
class BackupStoragePaths:
    """Absolute paths and portable keys for one generated backup identifier."""

    backup_root: Path
    project_ref: str
    backup_id: UUID
    artifact_path: Path
    manifest_path: Path
    artifact_key: str
    manifest_key: str


def normalize_project_ref(project_ref: UUID | str) -> str:
    """Return the canonical UUID string used as a storage namespace."""

    try:
        return str(UUID(str(project_ref)))
    except (AttributeError, ValueError) as exc:
        raise BackupPathError("Backup project reference must be a valid identifier.") from exc


def normalize_backup_relative_path(value: str) -> str:
    """Validate a relative POSIX path used inside a manifest or archive."""

    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise BackupPathError("Backup paths must be non-empty POSIX paths.")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise BackupPathError("Backup paths must not contain dot or empty segments.")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise BackupPathError("Backup paths must be normalized relative POSIX paths.")
    return value


def resolve_backup_root(root: Path | str) -> Path:
    """Create and resolve a private backup root that is not a symlink."""

    candidate = Path(root).expanduser()
    if candidate.is_symlink():
        raise BackupPathError("Backup root must not be a symlink.")
    try:
        candidate.mkdir(parents=True, exist_ok=True, mode=0o750)
    except OSError as exc:
        raise BackupArtifactError("Backup root could not be prepared.") from exc
    try:
        return resolve_approved_root(candidate)
    except (OSError, ValueError, NotADirectoryError, PermissionError) as exc:
        raise BackupPathError("Backup root is not a safe private directory.") from exc


def resolve_backup_roots(
    project_root: Path | str,
    backup_root: Path | str,
) -> tuple[Path, Path]:
    """Resolve source and backup roots and require separate storage trees."""

    source = resolve_approved_root(project_root)
    destination = resolve_backup_root(backup_root)
    if (
        source == destination
        or source.is_relative_to(destination)
        or destination.is_relative_to(source)
    ):
        raise BackupPathError("Backup storage must be separate from project storage.")
    return source, destination


def backup_storage_paths(
    backup_root: Path | str,
    project_ref: UUID | str,
    backup_id: UUID | str | None = None,
) -> BackupStoragePaths:
    """Return generated archive and manifest paths below the backup root."""

    root = resolve_backup_root(backup_root)
    normalized_ref = normalize_project_ref(project_ref)
    try:
        identifier = UUID(str(backup_id)) if backup_id is not None else uuid4()
    except ValueError as exc:
        raise BackupPathError("Backup identifier must be a valid UUID.") from exc
    project_directory = root / normalized_ref
    filename = str(identifier)
    return BackupStoragePaths(
        backup_root=root,
        project_ref=normalized_ref,
        backup_id=identifier,
        artifact_path=project_directory / f"{filename}{BACKUP_ARCHIVE_SUFFIX}",
        manifest_path=project_directory / f"{filename}{BACKUP_MANIFEST_SUFFIX}",
        artifact_key=f"{normalized_ref}/{filename}{BACKUP_ARCHIVE_SUFFIX}",
        manifest_key=f"{normalized_ref}/{filename}{BACKUP_MANIFEST_SUFFIX}",
    )


def _source_entry(root: Path, path: Path, kind: BackupEntryKind) -> BackupEntry:
    """Describe one source entry without following a symbolic link."""

    if path.is_symlink():
        raise BackupSourceError("Project backups do not follow symbolic links.")
    try:
        details = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise BackupSourceError("A project entry could not be inspected.") from exc

    if kind == "directory" and not stat.S_ISDIR(details.st_mode):
        raise BackupSourceError("Project directory state changed during backup.")
    if kind == "file" and not stat.S_ISREG(details.st_mode):
        raise BackupSourceError("Project backups support regular files only.")

    try:
        relative_path = normalize_backup_relative_path(
            path.relative_to(root).as_posix()
        )
    except (ValueError, BackupPathError) as exc:
        raise BackupSourceError("A project entry left the approved source root.") from exc

    if kind == "directory":
        return BackupEntry(
            relative_path=relative_path,
            kind=kind,
            size_bytes=0,
            checksum_sha256=None,
            mode=stat.S_IMODE(details.st_mode),
        )

    try:
        checksum = sha256_file(path)
        final_size = path.stat(follow_symlinks=False).st_size
    except OSError as exc:
        raise BackupSourceError("A project file could not be hashed.") from exc
    if final_size != details.st_size:
        raise BackupSourceError("A project file changed while it was being backed up.")
    return BackupEntry(
        relative_path=relative_path,
        kind=kind,
        size_bytes=details.st_size,
        checksum_sha256=checksum,
        mode=stat.S_IMODE(details.st_mode),
    )


def iter_project_entries(approved_root: Path | str) -> Iterable[BackupEntry]:
    """Yield every supported project directory and file in stable order."""

    root = resolve_approved_root(approved_root)
    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        directories.sort()
        filenames.sort()
        for name in directories:
            yield _source_entry(root, current_path / name, "directory")
        for name in filenames:
            yield _source_entry(root, current_path / name, "file")


def build_backup_manifest(
    approved_root: Path | str,
    project_ref: UUID | str,
) -> BackupManifest:
    """Build a versioned manifest from a project without writing to it."""

    entries = tuple(iter_project_entries(approved_root))
    return BackupManifest(
        format_version=BACKUP_FORMAT_VERSION,
        project_ref=normalize_project_ref(project_ref),
        entries=entries,
    )


__all__ = [
    "BACKUP_ARCHIVE_SUFFIX",
    "BACKUP_FORMAT_VERSION",
    "BACKUP_MANIFEST_SUFFIX",
    "DEFAULT_BACKUP_ROOT",
    "BackupDestinationExistsError",
    "BackupEntry",
    "BackupEntryKind",
    "BackupError",
    "BackupArtifactError",
    "BackupIntegrityError",
    "BackupManifest",
    "BackupPathError",
    "BackupSourceError",
    "BackupStoragePaths",
    "backup_storage_paths",
    "build_backup_manifest",
    "iter_project_entries",
    "normalize_backup_relative_path",
    "normalize_project_ref",
    "resolve_backup_root",
    "resolve_backup_roots",
]
