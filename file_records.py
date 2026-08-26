"""Persistence and search services for inventory-backed file records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from file_inventory import FileRecord
from models import File, FileHistory, FileVersion


ALLOWED_FILE_STATUSES = frozenset({"active", "missing", "archived"})


@dataclass(frozen=True)
class InventorySyncResult:
    """Result of one inventory-to-database synchronization."""

    records: tuple[File, ...]
    history_events: int
    versions_created: int


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for service events."""

    return datetime.now(timezone.utc)


def validate_storage_key(storage_key: str) -> str:
    """Validate a project-relative storage key without resolving host paths."""

    if not storage_key or "\\" in storage_key:
        raise ValueError("Storage key must be a non-empty POSIX relative path.")
    path = PurePosixPath(storage_key)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Storage key must remain inside the approved project root.")
    return path.as_posix()


def parse_inventory_timestamp(value: str) -> datetime:
    """Parse a scanner timestamp and normalize naive values to UTC."""

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _record_values(record: FileRecord) -> dict[str, object]:
    """Translate one scanner record to database column values."""

    storage_key = validate_storage_key(record.relative_path)
    return {
        "storage_key": storage_key,
        "name": record.name,
        "extension": record.extension,
        "media_type": record.mime_type,
        "size_bytes": record.size_bytes,
        "checksum_sha256": record.sha256.lower(),
        "modified_at": parse_inventory_timestamp(record.modified_at),
        "status": "active",
    }


def _values_equal(left: object, right: object) -> bool:
    """Compare persisted and scanned values without SQLite timezone noise."""

    if isinstance(left, datetime) and isinstance(right, datetime):
        if left.tzinfo is None:
            left = left.replace(tzinfo=timezone.utc)
        if right.tzinfo is None:
            right = right.replace(tzinfo=timezone.utc)
        return left.astimezone(timezone.utc) == right.astimezone(timezone.utc)
    return left == right


def _snapshot_changed(file_record: File, values: dict[str, object]) -> bool:
    """Return whether a newly observed scanner record differs from its snapshot."""

    return any(
        not _values_equal(getattr(file_record, key), value)
        for key, value in values.items()
    )


def _version_snapshot_changed(file_record: File, values: dict[str, object]) -> bool:
    """Return whether a new content/metadata version is required."""

    version_fields = (
        "storage_key",
        "name",
        "extension",
        "media_type",
        "size_bytes",
        "checksum_sha256",
        "modified_at",
    )
    return any(
        not _values_equal(getattr(file_record, key), values[key])
        for key in version_fields
    )


def _add_history(db: Session, file_record: File, event_code: str) -> None:
    """Append an immutable snapshot for a file lifecycle event."""

    db.add(
        FileHistory(
            file=file_record,
            event_code=event_code,
            storage_key=file_record.storage_key,
            name=file_record.name,
            extension=file_record.extension,
            media_type=file_record.media_type,
            size_bytes=file_record.size_bytes,
            checksum_sha256=file_record.checksum_sha256,
            modified_at=file_record.modified_at,
            status=file_record.status,
            observed_at=utc_now(),
        )
    )


def _add_version(
    db: Session,
    file_record: File,
    values: dict[str, object],
    version_number: int,
) -> None:
    """Append one immutable metadata version for a file."""

    db.add(
        FileVersion(
            file=file_record,
            version_number=version_number,
            storage_key=str(values["storage_key"]),
            media_type=str(values["media_type"]),
            size_bytes=int(values["size_bytes"]),
            checksum_sha256=str(values["checksum_sha256"]),
            modified_at=values["modified_at"],  # type: ignore[arg-type]
            is_original=version_number == 1,
        )
    )


def _next_version_number(file_record: File) -> int:
    """Return the next version number without reusing an old number."""

    return max(
        (version.version_number for version in file_record.versions),
        default=0,
    ) + 1


def sync_inventory_records(
    db: Session,
    project_id: UUID,
    records: list[FileRecord],
) -> InventorySyncResult:
    """Upsert scanned metadata and record changes without storing file contents.

    Records absent from a later scan are marked ``missing`` and receive a
    history event.  Existing records that reappear are restored to ``active``.
    The caller owns the transaction and must commit or roll back the session.
    """

    existing = {
        file_record.storage_key: file_record
        for file_record in db.scalars(
            select(File).where(File.project_id == project_id)
        ).all()
    }
    seen_keys: set[str] = set()
    persisted: list[File] = []
    history_events = 0
    versions_created = 0

    for record in records:
        values = _record_values(record)
        storage_key = str(values["storage_key"])
        if storage_key in seen_keys:
            raise ValueError(f"Duplicate inventory path: {storage_key}")
        seen_keys.add(storage_key)

        file_record = existing.get(storage_key)
        if file_record is None:
            file_record = File(project_id=project_id, **values)
            db.add(file_record)
            persisted.append(file_record)
            _add_history(db, file_record, "created")
            _add_version(db, file_record, values, 1)
            history_events += 1
            versions_created += 1
            continue

        if _snapshot_changed(file_record, values):
            event_code = "restored" if file_record.status == "missing" else "updated"
            version_changed = _version_snapshot_changed(file_record, values)
            for key, value in values.items():
                setattr(file_record, key, value)
            file_record.updated_at = utc_now()
            _add_history(db, file_record, event_code)
            history_events += 1
            if version_changed:
                _add_version(db, file_record, values, _next_version_number(file_record))
                versions_created += 1
        persisted.append(file_record)

    for file_record in existing.values():
        if file_record.storage_key not in seen_keys and file_record.status == "active":
            file_record.status = "missing"
            file_record.updated_at = utc_now()
            _add_history(db, file_record, "missing")
            history_events += 1

    db.flush()
    return InventorySyncResult(tuple(persisted), history_events, versions_created)


def build_file_search_statement(
    project_id: UUID,
    *,
    query: str | None = None,
    checksum_sha256: str | None = None,
    media_type: str | None = None,
    file_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Select[tuple[File]]:
    """Build a bounded, project-scoped file search statement."""

    if limit < 1 or limit > 100:
        raise ValueError("Search limit must be between 1 and 100.")
    if offset < 0:
        raise ValueError("Search offset must not be negative.")
    if file_status is not None and file_status not in ALLOWED_FILE_STATUSES:
        raise ValueError("Unsupported file status.")
    if checksum_sha256 is not None:
        normalized_checksum = checksum_sha256.lower()
        if len(normalized_checksum) != 64 or any(
            character not in "0123456789abcdef" for character in normalized_checksum
        ):
            raise ValueError("Checksum must be a 64-character SHA-256 value.")
        checksum_sha256 = normalized_checksum

    filters = [File.project_id == project_id]
    if query:
        pattern = f"%{query.strip()}%"
        filters.append(
            or_(
                File.name.ilike(pattern),
                File.storage_key.ilike(pattern),
                File.media_type.ilike(pattern),
            )
        )
    if checksum_sha256:
        filters.append(File.checksum_sha256 == checksum_sha256)
    if media_type:
        filters.append(File.media_type == media_type.strip())
    if file_status:
        filters.append(File.status == file_status)

    return (
        select(File)
        .where(and_(*filters))
        .order_by(File.updated_at.desc(), File.id)
        .offset(offset)
        .limit(limit)
    )


def build_file_history_statement(project_id: UUID, file_id: UUID) -> Select[tuple[FileHistory]]:
    """Build a project-scoped history query for one file."""

    return (
        select(FileHistory)
        .join(File, File.id == FileHistory.file_id)
        .where(File.project_id == project_id, FileHistory.file_id == file_id)
        .order_by(FileHistory.observed_at, FileHistory.id)
    )


def build_file_versions_statement(project_id: UUID, file_id: UUID) -> Select[tuple[FileVersion]]:
    """Build a project-scoped version query for one file."""

    return (
        select(FileVersion)
        .join(File, File.id == FileVersion.file_id)
        .where(File.project_id == project_id, FileVersion.file_id == file_id)
        .order_by(FileVersion.version_number)
    )


__all__ = [
    "ALLOWED_FILE_STATUSES",
    "InventorySyncResult",
    "build_file_history_statement",
    "build_file_search_statement",
    "build_file_versions_statement",
    "parse_inventory_timestamp",
    "sync_inventory_records",
    "validate_storage_key",
]
