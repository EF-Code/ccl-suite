from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from file_inventory import main as inventory_main
from file_organizer import main as organizer_main
from folder_generator import main as folder_main


def test_folder_generator_cli_creates_layout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "projects"
    monkeypatch.setattr(
        sys,
        "argv",
        ["folder_generator.py", "CLI Project", "--root", str(root)],
    )

    assert folder_main() == 0

    output = capsys.readouterr().out
    assert "Created project: cli-project" in output
    assert (root / "cli-project" / "incoming").is_dir()


def test_folder_generator_cli_reports_invalid_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["folder_generator.py", "../outside", "--root", str(tmp_path)],
    )

    with pytest.raises(SystemExit) as exc_info:
        folder_main()

    assert exc_info.value.code == 2


def test_inventory_cli_writes_manifests(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "notes.txt").write_text("notes", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["file_inventory.py", "--root", str(root)])

    assert inventory_main() == 0

    output = capsys.readouterr().out
    assert "Scanned 1 files." in output
    assert json.loads((root / "manifest.json").read_text(encoding="utf-8"))[0][
        "relative_path"
    ] == "notes.txt"
    assert (root / "manifest.csv").is_file()


def test_inventory_cli_reports_invalid_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["file_inventory.py", "--root", str(tmp_path / "missing")],
    )

    with pytest.raises(SystemExit) as exc_info:
        inventory_main()

    assert exc_info.value.code == 2


def test_organizer_cli_applies_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "project"
    incoming = root / "incoming"
    (root / "working").mkdir(parents=True)
    incoming.mkdir()
    source = incoming / "Notes.md"
    source.write_text("notes", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["file_organizer.py", str(root)])
    assert organizer_main() == 0
    assert "Plan written to organization-plan.json" in capsys.readouterr().out
    assert source.is_file()

    journal = root / "organization-journal.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["file_organizer.py", str(root), "--apply", "--journal", str(journal)],
    )
    assert organizer_main() == 0
    assert journal.is_file()
    assert not source.exists()

    monkeypatch.setattr(
        sys,
        "argv",
        ["file_organizer.py", str(root), "--rollback", str(journal)],
    )
    assert organizer_main() == 0
    assert "Rolled back 1 operation(s)." in capsys.readouterr().out
    assert source.read_text(encoding="utf-8") == "notes"


def test_organizer_cli_rejects_quarantine_without_apply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "project"
    (root / "incoming").mkdir(parents=True)
    (root / "working").mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        ["file_organizer.py", str(root), "--quarantine-conflicts"],
    )

    with pytest.raises(SystemExit) as exc_info:
        organizer_main()

    assert exc_info.value.code == 2
