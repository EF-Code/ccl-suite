from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database import Base
from file_inventory import FileRecord, sha256_file
from file_records import sync_inventory_records
from file_restore import (
    RestoreDestinationExistsError,
    UnsafeRestorePathError,
    restore_version_content,
    version_archive_path,
)
from models import FileVersion, Project, User


def make_session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'restore.sqlite3'}")
    Base.metadata.create_all(engine)
    return Session(engine)


def make_project(session: Session) -> Project:
    owner = User(external_ref="restore-owner")
    project = Project(
        owner=owner,
        name="Restore Project",
        storage_slug="restore-project",
    )
    session.add(project)
    session.commit()
    return project


def inventory_record(path: Path, root: Path) -> FileRecord:
    return FileRecord(
        relative_path=path.relative_to(root).as_posix(),
        name=path.name,
        extension=path.suffix,
        mime_type="text/plain",
        size_bytes=path.stat().st_size,
        modified_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        sha256=sha256_file(path),
        extension_mime_match=True,
    )


def test_restore_uses_archived_version_without_replacing_original(tmp_path: Path) -> None:
    root = tmp_path / "project"
    source = root / "incoming" / "notes.txt"
    source.parent.mkdir(parents=True)
    source.write_text("first version", encoding="utf-8")

    with make_session(tmp_path) as session:
        project = make_project(session)
        sync_inventory_records(
            session,
            project.id,
            [inventory_record(source, root)],
            approved_root=root,
        )
        session.commit()
        first_version = session.scalar(select(FileVersion))
        assert first_version is not None
        archive = version_archive_path(root, first_version.file_id, 1)
        assert archive.read_text(encoding="utf-8") == "first version"

        source.write_text("second version", encoding="utf-8")
        sync_inventory_records(
            session,
            project.id,
            [inventory_record(source, root)],
            approved_root=root,
        )
        session.commit()

        restored = restore_version_content(root, first_version, "output/notes-v1.txt")

    assert restored.destination_relative == Path("output/notes-v1.txt")
    assert (root / "output/notes-v1.txt").read_text(encoding="utf-8") == "first version"
    assert source.read_text(encoding="utf-8") == "second version"


def test_restore_rejects_original_and_existing_destinations(tmp_path: Path) -> None:
    root = tmp_path / "project"
    source = root / "incoming" / "notes.txt"
    source.parent.mkdir(parents=True)
    source.write_text("original", encoding="utf-8")

    with make_session(tmp_path) as session:
        project = make_project(session)
        sync_inventory_records(
            session,
            project.id,
            [inventory_record(source, root)],
            approved_root=root,
        )
        session.commit()
        version = session.scalar(select(FileVersion))
        assert version is not None

        with pytest.raises(UnsafeRestorePathError, match="differ"):
            restore_version_content(root, version, version.storage_key)

        destination = root / "output" / "existing.txt"
        destination.parent.mkdir()
        destination.write_text("keep", encoding="utf-8")
        with pytest.raises(RestoreDestinationExistsError):
            restore_version_content(root, version, "output/existing.txt")

        assert destination.read_text(encoding="utf-8") == "keep"
