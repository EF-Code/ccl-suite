"""Project-level backup contracts and storage-path safety helpers.

The backup implementation keeps archives outside project storage, stores only
relative artifact keys in the database, and treats every user-controlled path
as untrusted input.  Archive creation, verification, and restoration build on
the small immutable contracts defined here.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
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

    entries = tuple(
        sorted(
            iter_project_entries(approved_root),
            key=lambda entry: (entry.relative_path, entry.kind),
        )
    )
    return BackupManifest(
        format_version=BACKUP_FORMAT_VERSION,
        project_ref=normalize_project_ref(project_ref),
        entries=entries,
    )


def _entry_to_dict(entry: BackupEntry) -> dict[str, object]:
    """Translate one validated manifest entry to JSON-compatible data."""

    return {
        "checksum_sha256": entry.checksum_sha256,
        "kind": entry.kind,
        "mode": entry.mode,
        "relative_path": entry.relative_path,
        "size_bytes": entry.size_bytes,
    }


def _validate_manifest(manifest: BackupManifest) -> BackupManifest:
    """Validate and normalize a manifest before serialisation or use."""

    if manifest.format_version != BACKUP_FORMAT_VERSION:
        raise BackupIntegrityError("Unsupported backup manifest version.")
    project_ref = normalize_project_ref(manifest.project_ref)
    entries: list[BackupEntry] = []
    seen: dict[str, BackupEntryKind] = {}
    for entry in manifest.entries:
        relative_path = normalize_backup_relative_path(entry.relative_path)
        if entry.kind not in {"file", "directory"}:
            raise BackupIntegrityError("Backup manifest contains an unsupported entry kind.")
        if (
            not isinstance(entry.size_bytes, int)
            or isinstance(entry.size_bytes, bool)
            or entry.size_bytes < 0
        ):
            raise BackupIntegrityError("Backup manifest contains an invalid entry size.")
        if (
            not isinstance(entry.mode, int)
            or isinstance(entry.mode, bool)
            or entry.mode < 0
            or entry.mode > 0o777
        ):
            raise BackupIntegrityError("Backup manifest contains an invalid entry mode.")
        if entry.kind == "directory":
            if entry.size_bytes != 0 or entry.checksum_sha256 is not None:
                raise BackupIntegrityError("Directory entries must not contain file metadata.")
            checksum = None
        else:
            checksum = entry.checksum_sha256
            if (
                not isinstance(checksum, str)
                or len(checksum) != 64
                or checksum.lower() != checksum
                or any(character not in "0123456789abcdef" for character in checksum)
            ):
                raise BackupIntegrityError("File entries require a lowercase SHA-256 checksum.")
        if relative_path in seen:
            raise BackupIntegrityError("Backup manifest contains duplicate paths.")
        for index in range(1, len(relative_path.split("/"))):
            parent = "/".join(relative_path.split("/")[:index])
            if seen.get(parent) == "file":
                raise BackupIntegrityError("A file entry cannot contain child paths.")
        seen[relative_path] = entry.kind
        entries.append(
            BackupEntry(
                relative_path=relative_path,
                kind=entry.kind,
                size_bytes=entry.size_bytes,
                checksum_sha256=checksum,
                mode=entry.mode,
            )
        )

    ordered_entries = tuple(sorted(entries, key=lambda entry: (entry.relative_path, entry.kind)))
    if tuple(entries) != ordered_entries:
        raise BackupIntegrityError("Backup manifest entries must be sorted deterministically.")
    return BackupManifest(
        format_version=BACKUP_FORMAT_VERSION,
        project_ref=project_ref,
        entries=ordered_entries,
    )


def backup_manifest_bytes(manifest: BackupManifest) -> bytes:
    """Return canonical UTF-8 JSON bytes for a validated manifest."""

    validated = _validate_manifest(manifest)
    payload = {
        "entries": [_entry_to_dict(entry) for entry in validated.entries],
        "format_version": validated.format_version,
        "project_ref": validated.project_ref,
    }
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _manifest_from_payload(payload: object) -> BackupManifest:
    """Parse and strictly validate decoded JSON manifest data."""

    if not isinstance(payload, dict) or set(payload) != {
        "entries",
        "format_version",
        "project_ref",
    }:
        raise BackupIntegrityError("Backup manifest has an invalid top-level shape.")
    raw_entries = payload["entries"]
    if not isinstance(raw_entries, list):
        raise BackupIntegrityError("Backup manifest entries must be a list.")
    entries: list[BackupEntry] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict) or set(raw_entry) != {
            "checksum_sha256",
            "kind",
            "mode",
            "relative_path",
            "size_bytes",
        }:
            raise BackupIntegrityError("Backup manifest contains an invalid entry shape.")
        kind = raw_entry["kind"]
        if kind not in {"file", "directory"}:
            raise BackupIntegrityError("Backup manifest contains an unsupported entry kind.")
        entries.append(
            BackupEntry(
                relative_path=raw_entry["relative_path"],  # type: ignore[arg-type]
                kind=kind,
                size_bytes=raw_entry["size_bytes"],  # type: ignore[arg-type]
                checksum_sha256=raw_entry["checksum_sha256"],  # type: ignore[arg-type]
                mode=raw_entry["mode"],  # type: ignore[arg-type]
            )
        )
    return _validate_manifest(
        BackupManifest(
            format_version=payload["format_version"],  # type: ignore[arg-type]
            project_ref=payload["project_ref"],  # type: ignore[arg-type]
            entries=tuple(entries),
        )
    )


def read_backup_manifest(path: Path | str) -> tuple[BackupManifest, str]:
    """Read one manifest and return it with the checksum of its exact bytes."""

    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise BackupArtifactError("Backup manifest is unavailable.")
    try:
        raw = candidate.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupIntegrityError("Backup manifest could not be read safely.") from exc
    manifest = _manifest_from_payload(payload)
    return manifest, hashlib.sha256(raw).hexdigest()


def _write_new_bytes(destination: Path, payload: bytes, label: str) -> None:
    """Write bytes durably and publish them without replacing an existing path."""

    if destination.is_symlink():
        raise BackupArtifactError(f"{label} must not be a symlink.")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        if destination.parent.is_symlink():
            raise BackupPathError(f"{label} parent must not be a symlink.")
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=".backup-",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise BackupArtifactError(f"{label} already exists.") from exc
    except BackupError:
        raise
    except OSError as exc:
        raise BackupArtifactError(f"{label} could not be written safely.") from exc
    finally:
        if "temporary" in locals():
            temporary.unlink(missing_ok=True)


def write_backup_manifest(path: Path | str, manifest: BackupManifest) -> str:
    """Publish one canonical manifest and return its SHA-256 checksum."""

    payload = backup_manifest_bytes(manifest)
    _write_new_bytes(Path(path), payload, "Backup manifest")
    return hashlib.sha256(payload).hexdigest()


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
    "backup_manifest_bytes",
    "build_backup_manifest",
    "iter_project_entries",
    "normalize_backup_relative_path",
    "normalize_project_ref",
    "read_backup_manifest",
    "resolve_backup_root",
    "resolve_backup_roots",
    "write_backup_manifest",
]
