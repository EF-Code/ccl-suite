from pathlib import Path
import tarfile
from uuid import UUID, uuid4

import pytest

from file_backups import (
    BackupEntry,
    BackupIntegrityError,
    BackupManifest,
    BackupPathError,
    BackupSourceError,
    backup_storage_paths,
    backup_manifest_bytes,
    build_backup_manifest,
    create_backup,
    iter_project_entries,
    normalize_backup_relative_path,
    read_backup_manifest,
    resolve_backup_roots,
    write_backup_manifest,
)


def test_backup_roots_are_created_separately(tmp_path: Path) -> None:
    project_root = tmp_path / "projects"
    backup_root = tmp_path / "backups"
    project_root.mkdir()

    resolved_project, resolved_backup = resolve_backup_roots(project_root, backup_root)

    assert resolved_project == project_root.resolve()
    assert resolved_backup == backup_root.resolve()
    assert resolved_backup.is_dir()


def test_backup_root_must_not_be_inside_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "projects"
    project_root.mkdir()

    with pytest.raises(BackupPathError, match="separate"):
        resolve_backup_roots(project_root, project_root / "backups")


@pytest.mark.parametrize(
    "value",
    ["", "/absolute.txt", "../outside.txt", "nested/../file.txt", "nested\\file.txt", "./file.txt"],
)
def test_manifest_paths_reject_traversal_and_non_posix_forms(value: str) -> None:
    with pytest.raises(BackupPathError):
        normalize_backup_relative_path(value)


def test_storage_paths_use_uuid_names_and_relative_keys(tmp_path: Path) -> None:
    backup_root = tmp_path / "backups"
    project_id = uuid4()
    backup_id = uuid4()

    paths = backup_storage_paths(backup_root, project_id, backup_id)

    assert paths.backup_id == UUID(str(backup_id))
    assert paths.artifact_key == f"{project_id}/{backup_id}.tar"
    assert paths.manifest_key == f"{project_id}/{backup_id}.manifest.json"
    assert not Path(paths.artifact_key).is_absolute()
    assert paths.artifact_path == backup_root / str(project_id) / f"{backup_id}.tar"


def test_project_entries_include_directories_and_regular_files(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / "docs").mkdir(parents=True)
    (project_root / ".ccl-versions" / "file" ).mkdir(parents=True)
    (project_root / "README.md").write_text("read me", encoding="utf-8")
    (project_root / "docs" / "guide.txt").write_text("guide", encoding="utf-8")
    (project_root / ".ccl-versions" / "file" / "1").write_bytes(b"old")

    entries = list(iter_project_entries(project_root))

    assert [(entry.relative_path, entry.kind) for entry in entries] == [
        (".ccl-versions", "directory"),
        ("docs", "directory"),
        ("README.md", "file"),
        (".ccl-versions/file", "directory"),
        (".ccl-versions/file/1", "file"),
        ("docs/guide.txt", "file"),
    ]
    manifest = build_backup_manifest(project_root, uuid4())
    assert manifest.format_version == 1
    assert len(manifest.entries) == len(entries)


def test_project_entries_fail_closed_on_symbolic_links(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    link = project_root / "linked.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symbolic links are unavailable on this filesystem")

    with pytest.raises(BackupSourceError, match="symbolic links"):
        list(iter_project_entries(project_root))


def test_manifest_serialization_is_canonical_and_round_trips(tmp_path: Path) -> None:
    project_id = uuid4()
    manifest = BackupManifest(
        format_version=1,
        project_ref=str(project_id),
        entries=(
            BackupEntry("docs", "directory", 0, None, 0o750),
            BackupEntry(
                "docs/guide.txt",
                "file",
                5,
                "2bb80d537b1da3e38bd30361aa855686bde0ba1f3c0f9f7f2a3d2c2c9f0c0d3a",
                0o640,
            ),
        ),
    )

    payload = backup_manifest_bytes(manifest)
    manifest_path = tmp_path / "manifest.json"
    checksum = write_backup_manifest(manifest_path, manifest)
    loaded, loaded_checksum = read_backup_manifest(manifest_path)

    assert payload == manifest_path.read_bytes()
    assert checksum == loaded_checksum
    assert loaded == manifest


def test_manifest_rejects_duplicate_or_unsorted_entries() -> None:
    duplicate = BackupManifest(
        format_version=1,
        project_ref=str(uuid4()),
        entries=(
            BackupEntry("a.txt", "file", 1, "a" * 64, 0o640),
            BackupEntry("a.txt", "file", 1, "a" * 64, 0o640),
        ),
    )
    unsorted = BackupManifest(
        format_version=1,
        project_ref=str(uuid4()),
        entries=(
            BackupEntry("b.txt", "file", 1, "b" * 64, 0o640),
            BackupEntry("a.txt", "file", 1, "a" * 64, 0o640),
        ),
    )

    with pytest.raises(BackupIntegrityError, match="duplicate"):
        backup_manifest_bytes(duplicate)
    with pytest.raises(BackupIntegrityError, match="sorted"):
        backup_manifest_bytes(unsorted)


def test_create_backup_publishes_archive_and_preserves_project(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / "docs").mkdir(parents=True)
    (project_root / "docs" / "guide.txt").write_text("guide", encoding="utf-8")
    (project_root / "empty").mkdir()
    project_id = uuid4()
    original_bytes = (project_root / "docs" / "guide.txt").read_bytes()

    result = create_backup(project_root, tmp_path / "backups", project_id)

    assert result.file_count == 1
    assert result.total_bytes == len(original_bytes)
    assert result.archive_size_bytes == result.storage.artifact_path.stat().st_size
    assert result.storage.artifact_path.is_file()
    assert result.storage.manifest_path.is_file()
    assert (project_root / "docs" / "guide.txt").read_bytes() == original_bytes
    assert result.manifest_checksum_sha256
    assert result.archive_checksum_sha256
    with tarfile.open(result.storage.artifact_path, mode="r:") as archive:
        assert [member.name for member in archive.getmembers()] == [
            "docs",
            "docs/guide.txt",
            "empty",
        ]


def test_repeated_backup_has_stable_manifest_and_archive_bytes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "one.txt").write_text("same", encoding="utf-8")
    project_id = uuid4()

    first = create_backup(project_root, tmp_path / "backups", project_id)
    second = create_backup(project_root, tmp_path / "backups", project_id)

    assert first.storage.artifact_path.read_bytes() == second.storage.artifact_path.read_bytes()
    assert first.storage.manifest_path.read_bytes() == second.storage.manifest_path.read_bytes()
    assert first.archive_checksum_sha256 == second.archive_checksum_sha256
    assert first.manifest_checksum_sha256 == second.manifest_checksum_sha256
