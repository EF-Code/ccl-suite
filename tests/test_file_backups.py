from pathlib import Path
from uuid import UUID, uuid4

import pytest

from file_backups import (
    BackupPathError,
    backup_storage_paths,
    normalize_backup_relative_path,
    resolve_backup_roots,
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
