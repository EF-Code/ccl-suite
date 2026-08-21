import stat
from pathlib import Path

import pytest

from folder_generator import (
    PROJECT_DIRECTORY_MODE,
    PROJECT_SUBDIRECTORIES,
    create_project_folder,
    normalize_project_name,
)


def test_normalizes_display_name_to_kebab_case() -> None:
    assert normalize_project_name("  Client Intake Q3  ") == "client-intake-q3"
    assert normalize_project_name("Café Reports") == "cafe-reports"


def test_rejects_path_instructions() -> None:
    for unsafe_name in ("", ".", "..", "../outside", r"client\outside", "\x00bad"):
        with pytest.raises((TypeError, ValueError)):
            normalize_project_name(unsafe_name)

    with pytest.raises(TypeError, match="must be text"):
        normalize_project_name(123)  # type: ignore[arg-type]


def test_rejects_names_that_normalize_to_empty_or_are_too_long() -> None:
    with pytest.raises(ValueError, match="letter or number"):
        normalize_project_name("---")
    with pytest.raises(ValueError, match="at most"):
        normalize_project_name("a" * 65)


def test_creates_standard_layout_with_restrictive_modes(tmp_path) -> None:
    folders = create_project_folder("Client Intake Q3", tmp_path / "approved")

    assert folders.name == "client-intake-q3"
    assert folders.project == (tmp_path / "approved" / "client-intake-q3").resolve()
    assert tuple(path.name for path in folders.subdirectories) == PROJECT_SUBDIRECTORIES
    for directory in (folders.project, *folders.subdirectories):
        assert directory.is_dir()
        assert stat.S_IMODE(directory.stat().st_mode) & 0o007 == 0
        assert stat.S_IMODE(directory.stat().st_mode) & PROJECT_DIRECTORY_MODE == stat.S_IMODE(
            directory.stat().st_mode
        )


def test_collision_is_create_only_and_preserves_existing_content(tmp_path) -> None:
    folders = create_project_folder("Existing Project", tmp_path / "approved")
    marker = folders.working / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        create_project_folder("Existing Project", tmp_path / "approved")

    assert marker.read_text(encoding="utf-8") == "keep"


def test_rejects_world_writable_approved_root(tmp_path) -> None:
    root = tmp_path / "approved"
    root.mkdir()
    root.chmod(0o777)

    with pytest.raises(PermissionError, match="world-writable"):
        create_project_folder("Safe Project", root)


def test_rejects_file_as_approved_root(tmp_path) -> None:
    root = tmp_path / "not-a-directory"
    root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        create_project_folder("Safe Project", root)


def test_rejects_symlinked_approved_root(tmp_path) -> None:
    root = tmp_path / "approved"
    root.mkdir()
    alias = tmp_path / "approved-alias"
    alias.symlink_to(root, target_is_directory=True)

    with pytest.raises(ValueError, match="must not be a symlink"):
        create_project_folder("Safe Project", alias)


def test_rejects_filesystem_root_as_approved_location() -> None:
    with pytest.raises(ValueError, match="filesystem root"):
        create_project_folder("Safe Project", Path("/"))
