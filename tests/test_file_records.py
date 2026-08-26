from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database import Base
from file_inventory import FileRecord
from file_records import (
    build_file_search_statement,
    sync_inventory_records,
    validate_storage_key,
)
from models import File, FileHistory, FileVersion, Project, User


def make_session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'records.sqlite3'}")
    Base.metadata.create_all(engine)
    return Session(engine)


def make_project(session: Session) -> Project:
    owner = User(external_ref="records-owner")
    project = Project(owner=owner, name="Records Project")
    session.add(project)
    session.commit()
    return project


def inventory_record(
    relative_path: str = "incoming/report.txt",
    *,
    contents_hash: str = "a" * 64,
    size_bytes: int = 4,
) -> FileRecord:
    return FileRecord(
        relative_path=relative_path,
        name=Path(relative_path).name,
        extension=Path(relative_path).suffix,
        mime_type="text/plain",
        size_bytes=size_bytes,
        modified_at=datetime.now(timezone.utc).isoformat(),
        sha256=contents_hash,
        extension_mime_match=True,
    )


def test_sync_persists_metadata_and_creation_history(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        project = make_project(session)

        result = sync_inventory_records(
            session,
            project.id,
            [inventory_record()],
        )
        session.commit()

        assert result.history_events == 1
        assert result.versions_created == 1
        file_record = session.scalar(select(File))
        assert file_record is not None
        assert file_record.storage_key == "incoming/report.txt"
        assert file_record.name == "report.txt"
        assert file_record.status == "active"
        history = session.scalars(select(FileHistory)).all()
        assert [entry.event_code for entry in history] == ["created"]


def test_file_versions_are_linked_and_ordered_per_file(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        project = make_project(session)
        sync_inventory_records(session, project.id, [inventory_record()])
        session.commit()
        file_record = session.scalar(select(File))
        assert file_record is not None
        assert [version.version_number for version in file_record.versions] == [1]

        session.add(
            FileVersion(
                file=file_record,
                version_number=2,
                storage_key=file_record.storage_key,
                media_type=file_record.media_type,
                size_bytes=8,
                checksum_sha256="b" * 64,
                modified_at=file_record.modified_at,
                is_original=False,
            )
        )
        session.commit()
        session.refresh(file_record)

        assert [version.version_number for version in file_record.versions] == [1, 2]
        assert file_record.versions[0].is_original is True


def test_sync_records_updates_missing_and_restores_files(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        project = make_project(session)
        original = inventory_record()
        sync_inventory_records(session, project.id, [original])
        session.commit()

        missing_result = sync_inventory_records(session, project.id, [])
        session.commit()
        file_record = session.scalar(select(File))
        assert file_record is not None
        assert file_record.status == "missing"
        assert missing_result.history_events == 1

        restored_result = sync_inventory_records(
            session,
            project.id,
            [inventory_record(contents_hash="b" * 64, size_bytes=5)],
        )
        session.commit()
        assert restored_result.history_events == 1
        assert file_record.status == "active"
        assert file_record.checksum_sha256 == "b" * 64
        assert [entry.event_code for entry in session.scalars(select(FileHistory)).all()] == [
            "created",
            "missing",
            "restored",
        ]
        versions = session.scalars(
            select(FileVersion).order_by(FileVersion.version_number)
        ).all()
        assert [version.version_number for version in versions] == [1, 2]
        assert versions[0].checksum_sha256 == "a" * 64
        assert versions[1].checksum_sha256 == "b" * 64


def test_sync_creates_versions_only_for_changed_snapshots(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        project = make_project(session)
        first = inventory_record()
        initial = sync_inventory_records(session, project.id, [first])
        session.commit()

        unchanged = sync_inventory_records(session, project.id, [first])
        session.commit()
        changed = sync_inventory_records(
            session,
            project.id,
            [inventory_record(contents_hash="c" * 64, size_bytes=7)],
        )
        session.commit()

        assert initial.versions_created == 1
        assert unchanged.versions_created == 0
        assert changed.versions_created == 1
        versions = session.scalars(
            select(FileVersion).order_by(FileVersion.version_number)
        ).all()
        assert [version.version_number for version in versions] == [1, 2]
        assert [version.checksum_sha256 for version in versions] == [
            "a" * 64,
            "c" * 64,
        ]


def test_search_statement_is_project_scoped_and_filterable(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        project = make_project(session)
        other_project = Project(name="Other Project", owner_id=project.owner_id)
        session.add(other_project)
        session.commit()
        sync_inventory_records(
            session,
            project.id,
            [inventory_record()],
        )
        sync_inventory_records(
            session,
            other_project.id,
            [inventory_record(relative_path="incoming/report.txt", contents_hash="c" * 64)],
        )
        session.commit()

        results = session.scalars(
            build_file_search_statement(project.id, query="report", file_status="active")
        ).all()

        assert len(results) == 1
        assert results[0].project_id == project.id
        assert results[0].checksum_sha256 == "a" * 64


def test_sync_rejects_duplicate_inventory_paths(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        project = make_project(session)
        duplicate = inventory_record()

        with pytest.raises(ValueError, match="Duplicate inventory path"):
            sync_inventory_records(session, project.id, [duplicate, duplicate])


@pytest.mark.parametrize("value", ["/absolute.txt", "../outside.txt", "incoming\\file.txt", ""])
def test_validate_storage_key_rejects_unsafe_paths(value: str) -> None:
    with pytest.raises(ValueError):
        validate_storage_key(value)
