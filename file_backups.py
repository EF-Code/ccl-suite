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
import shutil
import stat
import tarfile
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


@dataclass(frozen=True)
class BackupArtifact:
    """Durably published archive metadata returned by backup creation."""

    storage: BackupStoragePaths
    manifest: BackupManifest
    archive_size_bytes: int
    archive_checksum_sha256: str
    manifest_checksum_sha256: str
    file_count: int
    total_bytes: int

    @property
    def artifact_key(self) -> str:
        """Return the portable archive key persisted by the API."""

        return self.storage.artifact_key

    @property
    def manifest_key(self) -> str:
        """Return the portable manifest key persisted by the API."""

        return self.storage.manifest_key


@dataclass(frozen=True)
class BackupVerification:
    """Evidence returned after checking an archive against its manifest."""

    manifest: BackupManifest
    archive_checksum_sha256: str
    manifest_checksum_sha256: str
    entries_verified: int
    file_count: int
    bytes_verified: int


@dataclass(frozen=True)
class BackupRestoreResult:
    """Details about one verified project copy published by restoration."""

    root: Path
    destination: Path
    entries_restored: int
    file_count: int
    bytes_restored: int
    archive_checksum_sha256: str
    manifest_checksum_sha256: str

    @property
    def destination_relative(self) -> Path:
        """Return the restored path relative to its approved parent."""

        from file_inventory import safe_relative_path

        return safe_relative_path(self.root, self.destination)


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
            parent_kind = seen.get(parent)
            if parent_kind == "file":
                raise BackupIntegrityError("A file entry cannot contain child paths.")
            if parent_kind is None:
                raise BackupIntegrityError("Every manifest child must have a directory entry.")
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


def _safe_source_path(root: Path, relative_path: str, kind: BackupEntryKind) -> Path:
    """Resolve a manifest path while rejecting symlink components."""

    normalized = normalize_backup_relative_path(relative_path)
    candidate = root.joinpath(*normalized.split("/"))
    current = root
    for part in normalized.split("/"):
        current = current / part
        if current.is_symlink():
            raise BackupSourceError("Project backups do not follow symbolic links.")
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise BackupSourceError("A project entry left the approved source root.")
    if kind == "directory" and not resolved.is_dir():
        raise BackupSourceError("A project directory is no longer available.")
    if kind == "file" and not resolved.is_file():
        raise BackupSourceError("A project file is no longer available.")
    return resolved


def _tar_info(entry: BackupEntry) -> tarfile.TarInfo:
    """Create stable tar metadata without host-specific ownership or times."""

    info = tarfile.TarInfo(name=entry.relative_path)
    info.type = tarfile.DIRTYPE if entry.kind == "directory" else tarfile.REGTYPE
    info.mode = entry.mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.size = entry.size_bytes if entry.kind == "file" else 0
    return info


class _HashingReader:
    """Bounded reader that hashes exactly the bytes copied into an archive."""

    def __init__(self, stream: object) -> None:
        self.stream = stream
        self.digest = hashlib.sha256()
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        """Read and hash one tarfile chunk."""

        chunk = self.stream.read(size)  # type: ignore[union-attr]
        if not isinstance(chunk, bytes):
            raise BackupSourceError("Project file could not be read as bytes.")
        self.digest.update(chunk)
        self.bytes_read += len(chunk)
        return chunk


def _publish_temporary_file(temporary: Path, destination: Path, label: str) -> None:
    """Publish a temporary file through a no-overwrite hard link."""

    if destination.is_symlink():
        raise BackupArtifactError(f"{label} must not be a symlink.")
    if destination.parent.is_symlink():
        raise BackupPathError(f"{label} parent must not be a symlink.")
    try:
        os.link(temporary, destination)
    except FileExistsError as exc:
        raise BackupArtifactError(f"{label} already exists.") from exc
    except OSError as exc:
        raise BackupArtifactError(f"{label} could not be published safely.") from exc


def _prepare_artifact_directory(storage: BackupStoragePaths) -> None:
    """Create the per-project artifact directory without following links."""

    parent = storage.artifact_path.parent
    if parent.is_symlink():
        raise BackupPathError("Backup artifact directory must not be a symlink.")
    parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    if parent.is_symlink() or not parent.is_dir():
        raise BackupPathError("Backup artifact directory is not safe.")
    if not parent.resolve(strict=False).is_relative_to(storage.backup_root):
        raise BackupPathError("Backup artifact directory left the backup root.")


def _create_archive(
    root: Path,
    manifest: BackupManifest,
    destination: Path,
) -> tuple[int, str]:
    """Create and publish one deterministic tar archive."""

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=".backup-",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
        with tarfile.open(temporary, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for entry in manifest.entries:
                source = _safe_source_path(root, entry.relative_path, entry.kind)
                info = _tar_info(entry)
                if entry.kind == "directory":
                    archive.addfile(info)
                    continue
                try:
                    with source.open("rb") as source_stream:
                        reader = _HashingReader(source_stream)
                        archive.addfile(info, reader)
                except OSError as exc:
                    raise BackupSourceError("A project file could not be archived.") from exc
                if reader.bytes_read != entry.size_bytes or reader.digest.hexdigest() != entry.checksum_sha256:
                    raise BackupSourceError("A project file changed during backup.")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        _publish_temporary_file(temporary, destination, "Backup archive")
        return destination.stat().st_size, sha256_file(destination)
    except BackupError:
        raise
    except (OSError, tarfile.TarError) as exc:
        raise BackupArtifactError("Backup archive could not be created safely.") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def create_backup(
    project_root: Path | str,
    backup_root: Path | str,
    project_ref: UUID | str,
    backup_id: UUID | str | None = None,
) -> BackupArtifact:
    """Create a manifest and deterministic archive without modifying a project."""

    root, destination_root = resolve_backup_roots(project_root, backup_root)
    storage = backup_storage_paths(destination_root, project_ref, backup_id)
    _prepare_artifact_directory(storage)
    manifest = build_backup_manifest(root, storage.project_ref)
    archive_published = False
    manifest_published = False
    try:
        archive_size, archive_checksum = _create_archive(
            root,
            manifest,
            storage.artifact_path,
        )
        archive_published = True
        manifest_checksum = write_backup_manifest(storage.manifest_path, manifest)
        manifest_published = True
    except BackupError:
        if archive_published:
            storage.artifact_path.unlink(missing_ok=True)
        if manifest_published:
            storage.manifest_path.unlink(missing_ok=True)
        raise
    return BackupArtifact(
        storage=storage,
        manifest=manifest,
        archive_size_bytes=archive_size,
        archive_checksum_sha256=archive_checksum,
        manifest_checksum_sha256=manifest_checksum,
        file_count=sum(entry.kind == "file" for entry in manifest.entries),
        total_bytes=sum(entry.size_bytes for entry in manifest.entries if entry.kind == "file"),
    )


def _validate_expected_checksum(value: str | None, label: str) -> str | None:
    """Validate an optional persisted SHA-256 checksum."""

    if value is None:
        return None
    if (
        len(value) != 64
        or value.lower() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise BackupIntegrityError(f"{label} is not a valid SHA-256 checksum.")
    return value


def _archive_member_kind(member: tarfile.TarInfo) -> BackupEntryKind:
    """Allow only the regular files and directories emitted by this module."""

    if member.isdir():
        return "directory"
    if member.isreg():
        return "file"
    raise BackupIntegrityError("Backup archive contains an unsupported member type.")


def _verify_archive_members(
    archive_path: Path,
    manifest: BackupManifest,
) -> tuple[int, int, int]:
    """Verify every tar member and return entries, files, and bytes checked."""

    expected = {entry.relative_path: entry for entry in manifest.entries}
    seen: set[str] = set()
    entries_verified = 0
    file_count = 0
    bytes_verified = 0
    try:
        with tarfile.open(archive_path, mode="r:") as archive:
            for member in archive:
                try:
                    normalized_name = normalize_backup_relative_path(member.name)
                except BackupPathError as exc:
                    raise BackupIntegrityError("Backup archive contains an unsafe path.") from exc
                if normalized_name != member.name or normalized_name in seen:
                    raise BackupIntegrityError("Backup archive contains duplicate or non-normalized paths.")
                entry = expected.get(normalized_name)
                if entry is None:
                    raise BackupIntegrityError("Backup archive contains an unexpected path.")
                member_kind = _archive_member_kind(member)
                if member_kind != entry.kind or stat.S_IMODE(member.mode) != entry.mode:
                    raise BackupIntegrityError("Backup archive metadata differs from its manifest.")
                if entry.kind == "directory":
                    if member.size != 0:
                        raise BackupIntegrityError("Backup directory metadata contains bytes.")
                else:
                    if member.size != entry.size_bytes:
                        raise BackupIntegrityError("Backup archive file size differs from its manifest.")
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise BackupIntegrityError("Backup archive file could not be read.")
                    digest = hashlib.sha256()
                    size = 0
                    with stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                            size += len(chunk)
                    if size != entry.size_bytes or digest.hexdigest() != entry.checksum_sha256:
                        raise BackupIntegrityError("Backup archive file checksum differs from its manifest.")
                    file_count += 1
                    bytes_verified += size
                seen.add(normalized_name)
                entries_verified += 1
    except BackupIntegrityError:
        raise
    except (OSError, tarfile.TarError) as exc:
        raise BackupIntegrityError("Backup archive could not be read safely.") from exc
    if seen != set(expected):
        raise BackupIntegrityError("Backup archive is missing manifest entries.")
    return entries_verified, file_count, bytes_verified


def verify_backup(
    storage: BackupStoragePaths,
    *,
    expected_archive_checksum: str | None = None,
    expected_manifest_checksum: str | None = None,
    expected_project_ref: UUID | str | None = None,
) -> BackupVerification:
    """Verify artifact files, manifest structure, and every archived file hash."""

    expected_archive_checksum = _validate_expected_checksum(
        expected_archive_checksum,
        "Archive checksum",
    )
    expected_manifest_checksum = _validate_expected_checksum(
        expected_manifest_checksum,
        "Manifest checksum",
    )
    if storage.artifact_path.is_symlink() or not storage.artifact_path.is_file():
        raise BackupArtifactError("Backup archive is unavailable.")
    if storage.manifest_path.is_symlink() or not storage.manifest_path.is_file():
        raise BackupArtifactError("Backup manifest is unavailable.")
    try:
        archive_checksum = sha256_file(storage.artifact_path)
    except OSError as exc:
        raise BackupArtifactError("Backup archive checksum could not be read.") from exc
    if expected_archive_checksum is not None and archive_checksum != expected_archive_checksum:
        raise BackupIntegrityError("Backup archive checksum verification failed.")
    manifest, manifest_checksum = read_backup_manifest(storage.manifest_path)
    if expected_manifest_checksum is not None and manifest_checksum != expected_manifest_checksum:
        raise BackupIntegrityError("Backup manifest checksum verification failed.")
    if expected_project_ref is not None and manifest.project_ref != normalize_project_ref(expected_project_ref):
        raise BackupIntegrityError("Backup manifest belongs to a different project.")
    entries_verified, file_count, bytes_verified = _verify_archive_members(
        storage.artifact_path,
        manifest,
    )
    return BackupVerification(
        manifest=manifest,
        archive_checksum_sha256=archive_checksum,
        manifest_checksum_sha256=manifest_checksum,
        entries_verified=entries_verified,
        file_count=file_count,
        bytes_verified=bytes_verified,
    )


def _resolve_restore_destination(root: Path, destination: Path | str) -> Path:
    """Resolve a new restore directory below an approved parent."""

    if not isinstance(destination, (Path, str)):
        raise BackupPathError("Restore destination must be a relative path.")
    raw_destination = str(destination)
    try:
        normalized = normalize_backup_relative_path(raw_destination)
    except BackupPathError as exc:
        raise BackupPathError("Restore destination must be a normalized relative path.") from exc
    candidate = root.joinpath(*normalized.split("/"))
    current = root
    for part in normalized.split("/")[:-1]:
        current = current / part
        if current.is_symlink():
            raise BackupPathError("Restore destination must not contain symlink components.")
        if current.exists() and not current.is_dir():
            raise BackupPathError("Restore destination parent must be a directory.")
    if candidate.is_symlink() or candidate.exists():
        raise BackupDestinationExistsError(
            "Restore destination already exists and will not be overwritten."
        )
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise BackupPathError("Restore destination must remain inside the approved parent.")
    return resolved


def _ensure_restore_parent(root: Path, destination: Path) -> None:
    """Create missing destination parents while rejecting symlink races."""

    relative_parent = destination.parent.relative_to(root)
    current = root
    for part in relative_parent.parts:
        current = current / part
        if current.is_symlink():
            raise BackupPathError("Restore destination parent must not be a symlink.")
        if current.exists():
            if not current.is_dir():
                raise BackupPathError("Restore destination parent must be a directory.")
        else:
            current.mkdir(mode=0o750)


def _stage_path(staging: Path, relative_path: str) -> Path:
    """Resolve an archive entry below a newly-created staging directory."""

    normalized = normalize_backup_relative_path(relative_path)
    candidate = staging.joinpath(*normalized.split("/"))
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(staging):
        raise BackupIntegrityError("Backup archive path escaped its staging directory.")
    return resolved


def _ensure_stage_directory(path: Path, mode: int) -> None:
    """Create one extracted directory without replacing anything."""

    if path.is_symlink():
        raise BackupIntegrityError("Backup archive attempted to create a symlink.")
    if path.exists():
        if not path.is_dir():
            raise BackupIntegrityError("Backup archive contains a file-directory collision.")
    else:
        try:
            path.mkdir(mode=mode)
        except OSError as exc:
            raise BackupIntegrityError("Backup directory could not be extracted safely.") from exc
    try:
        os.chmod(path, mode)
    except OSError as exc:
        raise BackupIntegrityError("Backup directory permissions could not be applied.") from exc


def _ensure_stage_parent(path: Path) -> None:
    """Ensure a file's already-approved parent exists without changing its mode."""

    if path.is_symlink():
        raise BackupIntegrityError("Backup archive attempted to create a symlink.")
    if path.exists():
        if not path.is_dir():
            raise BackupIntegrityError("Backup archive contains a file-directory collision.")
        return
    try:
        path.mkdir(mode=0o750)
    except OSError as exc:
        raise BackupIntegrityError("Backup file parent could not be created safely.") from exc


def _extract_archive_to_stage(
    storage: BackupStoragePaths,
    manifest: BackupManifest,
    staging: Path,
) -> tuple[int, int, int]:
    """Extract only manifest-approved members into a new staging directory."""

    expected = {entry.relative_path: entry for entry in manifest.entries}
    seen: set[str] = set()
    entries_restored = 0
    file_count = 0
    bytes_restored = 0
    try:
        with tarfile.open(storage.artifact_path, mode="r:") as archive:
            for member in archive:
                try:
                    normalized_name = normalize_backup_relative_path(member.name)
                except BackupPathError as exc:
                    raise BackupIntegrityError("Backup archive contains an unsafe path.") from exc
                if normalized_name != member.name or normalized_name in seen:
                    raise BackupIntegrityError("Backup archive contains duplicate or non-normalized paths.")
                entry = expected.get(normalized_name)
                if entry is None:
                    raise BackupIntegrityError("Backup archive contains an unexpected path.")
                if _archive_member_kind(member) != entry.kind:
                    raise BackupIntegrityError("Backup archive member kind differs from its manifest.")
                target = _stage_path(staging, normalized_name)
                if entry.kind == "directory":
                    if member.size != 0:
                        raise BackupIntegrityError("Backup directory metadata contains bytes.")
                    _ensure_stage_directory(target, entry.mode)
                else:
                    if member.size != entry.size_bytes:
                        raise BackupIntegrityError("Backup archive file size differs from its manifest.")
                    _ensure_stage_parent(target.parent)
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise BackupIntegrityError("Backup archive file could not be read.")
                    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                    try:
                        descriptor = os.open(target, flags, entry.mode)
                    except OSError as exc:
                        raise BackupIntegrityError("Backup file could not be extracted safely.") from exc
                    digest = hashlib.sha256()
                    size = 0
                    try:
                        with os.fdopen(descriptor, "wb") as output:
                            with stream:
                                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                                    digest.update(chunk)
                                    size += len(chunk)
                                    output.write(chunk)
                            output.flush()
                            os.fsync(output.fileno())
                    except (OSError, tarfile.TarError) as exc:
                        raise BackupIntegrityError("Backup file could not be extracted safely.") from exc
                    if size != entry.size_bytes or digest.hexdigest() != entry.checksum_sha256:
                        raise BackupIntegrityError("Extracted backup file failed checksum verification.")
                    os.chmod(target, entry.mode)
                    file_count += 1
                    bytes_restored += size
                seen.add(normalized_name)
                entries_restored += 1
    except BackupIntegrityError:
        raise
    except (OSError, tarfile.TarError) as exc:
        raise BackupIntegrityError("Backup archive could not be extracted safely.") from exc
    if seen != set(expected):
        raise BackupIntegrityError("Backup archive is missing manifest entries.")
    return entries_restored, file_count, bytes_restored


def _verify_staged_tree(staging: Path, manifest: BackupManifest) -> None:
    """Re-scan the extracted tree and compare every entry to its manifest."""

    observed = tuple(
        sorted(
            iter_project_entries(staging),
            key=lambda entry: (entry.relative_path, entry.kind),
        )
    )
    if observed != manifest.entries:
        raise BackupIntegrityError("Restored project tree differs from its manifest.")


def _publish_restore_directory(staging: Path, destination: Path) -> None:
    """Publish a verified staging directory after a no-overwrite check."""

    if destination.is_symlink() or destination.exists():
        raise BackupDestinationExistsError(
            "Restore destination already exists and will not be overwritten."
        )
    try:
        os.rename(staging, destination)
    except FileExistsError as exc:
        raise BackupDestinationExistsError(
            "Restore destination already exists and will not be overwritten."
        ) from exc
    except OSError as exc:
        raise BackupArtifactError("Restored project could not be published safely.") from exc


def restore_backup(
    storage: BackupStoragePaths,
    approved_parent: Path | str,
    destination: Path | str,
    *,
    expected_archive_checksum: str | None = None,
    expected_manifest_checksum: str | None = None,
    expected_project_ref: UUID | str | None = None,
) -> BackupRestoreResult:
    """Verify and restore a project backup to a new directory."""

    root = resolve_approved_root(approved_parent)
    destination_path = _resolve_restore_destination(root, destination)
    verification = verify_backup(
        storage,
        expected_archive_checksum=expected_archive_checksum,
        expected_manifest_checksum=expected_manifest_checksum,
        expected_project_ref=expected_project_ref,
    )
    _ensure_restore_parent(root, destination_path)
    staging = destination_path.parent / f".ccl-restore-{uuid4().hex}"
    if staging.exists() or staging.is_symlink():
        raise BackupArtifactError("A restore staging path already exists.")
    try:
        staging.mkdir(mode=0o700)
        entries_restored, file_count, bytes_restored = _extract_archive_to_stage(
            storage,
            verification.manifest,
            staging,
        )
        _verify_staged_tree(staging, verification.manifest)
        _publish_restore_directory(staging, destination_path)
    except BackupError:
        if staging.exists() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise
    except OSError as exc:
        if staging.exists() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise BackupArtifactError("Restored project could not be completed safely.") from exc
    return BackupRestoreResult(
        root=root,
        destination=destination_path,
        entries_restored=entries_restored,
        file_count=file_count,
        bytes_restored=bytes_restored,
        archive_checksum_sha256=verification.archive_checksum_sha256,
        manifest_checksum_sha256=verification.manifest_checksum_sha256,
    )


__all__ = [
    "BACKUP_ARCHIVE_SUFFIX",
    "BACKUP_FORMAT_VERSION",
    "BACKUP_MANIFEST_SUFFIX",
    "DEFAULT_BACKUP_ROOT",
    "BackupDestinationExistsError",
    "BackupArtifact",
    "BackupEntry",
    "BackupEntryKind",
    "BackupError",
    "BackupArtifactError",
    "BackupIntegrityError",
    "BackupManifest",
    "BackupPathError",
    "BackupSourceError",
    "BackupStoragePaths",
    "BackupVerification",
    "BackupRestoreResult",
    "backup_storage_paths",
    "backup_manifest_bytes",
    "build_backup_manifest",
    "create_backup",
    "iter_project_entries",
    "normalize_backup_relative_path",
    "normalize_project_ref",
    "read_backup_manifest",
    "resolve_backup_root",
    "resolve_backup_roots",
    "restore_backup",
    "verify_backup",
    "write_backup_manifest",
]
