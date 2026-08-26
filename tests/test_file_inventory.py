from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from file_inventory import (
    detect_mime_type,
    extension_mime_match,
    scan_files,
    write_manifests,
)


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


def test_scan_rejects_non_directory_root(tmp_path: Path) -> None:
    root = tmp_path / "not-a-directory"
    root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(NotADirectoryError, match="not a directory"):
        scan_files(root)


def test_scan_skips_symlinked_files(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    target = root / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = root / "link.txt"
    link.symlink_to(target)

    records = scan_files(root)

    assert [record.relative_path for record in records] == ["target.txt"]


def test_mime_detection_falls_back_when_file_command_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "unknown.bin"
    source.write_bytes(b"data")

    class FailedCommand:
        returncode = 1
        stdout = ""

    monkeypatch.setattr("file_inventory.subprocess.run", lambda *args, **kwargs: FailedCommand())

    assert detect_mime_type(source) == "application/octet-stream"


def test_unknown_extension_has_no_mime_match_expectation(tmp_path: Path) -> None:
    assert extension_mime_match(tmp_path / "file.unknown", "text/plain") is None


def test_manifest_paths_reject_symlink_same_and_external_outputs(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    target = root / "target.json"
    target.write_text("keep", encoding="utf-8")
    symlink = root / "manifest.json"
    symlink.symlink_to(target)

    with pytest.raises(ValueError, match="must not be a symlink"):
        write_manifests(root, [], json_path=symlink)

    same = root / "same.json"
    with pytest.raises(ValueError, match="must be different"):
        write_manifests(root, [], json_path=same, csv_path=same)

    with pytest.raises(ValueError, match="inside the approved root"):
        write_manifests(root, [], json_path=tmp_path / "outside.json")


def test_scanner_excludes_private_version_archives(tmp_path: Path) -> None:
    root = tmp_path / "project"
    visible = root / "incoming" / "notes.txt"
    hidden = root / ".ccl-versions" / "file-id" / "1"
    visible.parent.mkdir(parents=True)
    hidden.parent.mkdir(parents=True)
    visible.write_text("visible", encoding="utf-8")
    hidden.write_text("archived", encoding="utf-8")

    records = scan_files(root)

    assert [record.relative_path for record in records] == ["incoming/notes.txt"]
