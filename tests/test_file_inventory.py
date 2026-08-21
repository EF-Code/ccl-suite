from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from file_inventory import scan_files


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    return root


def test_empty_file_is_recorded_with_zero_size_and_sha256(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    empty = root / "empty.txt"
    empty.touch()

    records = scan_files(root)

    assert len(records) == 1
    assert records[0].relative_path == "empty.txt"
    assert records[0].size_bytes == 0
    assert records[0].sha256 == hashlib.sha256(b"").hexdigest()


def test_identical_files_have_the_same_duplicate_hash(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    (root / "one.txt").write_text("same", encoding="utf-8")
    (root / "two.txt").write_text("same", encoding="utf-8")

    records = scan_files(root)

    assert len(records) == 2
    assert records[0].sha256 == records[1].sha256
    assert len({record.sha256 for record in records}) == 1


def test_misleading_extension_is_reported_as_a_mime_mismatch(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    misleading = root / "photo.jpg"
    misleading.write_text("plain text, not an image", encoding="utf-8")

    records = scan_files(root)

    assert records[0].extension == ".jpg"
    assert records[0].extension_mime_match is False


def test_scan_rejects_symlinked_root(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    alias = tmp_path / "project-alias"
    alias.symlink_to(root, target_is_directory=True)

    with pytest.raises(ValueError, match="must not be a symlink"):
        scan_files(alias)


def test_scan_rejects_world_writable_root(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    root.chmod(0o777)

    with pytest.raises(PermissionError, match="world-writable"):
        scan_files(root)
