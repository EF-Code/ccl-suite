from __future__ import annotations

import json
from pathlib import Path

import pytest

from file_organizer import (
    JournalEntry,
    OrganizationAction,
    OrganizationPlan,
    apply_plan,
    build_plan,
    load_journal,
    move_without_overwrite,
    normalize_filename,
    quarantine_conflicts,
    render_plan,
    rollback_journal,
    write_journal,
    write_plan,
)


def make_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "project"
    source = root / "incoming"
    target = root / "working"
    source.mkdir(parents=True)
    target.mkdir()
    return root, source, target


def test_normalize_filename_keeps_extension_and_removes_path_components() -> None:
    assert normalize_filename("Résumé Q3!.CSV") == "resume-q3.csv"

    with pytest.raises(ValueError, match="path components"):
        normalize_filename("../report.csv")

    with pytest.raises(ValueError, match="letters or numbers"):
        normalize_filename("---.csv")


def test_build_plan_is_dry_run_and_writes_confined_plan(tmp_path: Path) -> None:
    root, source, target = make_project(tmp_path)
    report = source / "Quarterly Report.csv"
    report.write_text("name,total\nalpha,3\n", encoding="utf-8")

    plan = build_plan(root)

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.status == "planned"
    assert action.destination == "working/spreadsheets/quarterly-report.csv"
    assert report.is_file()
    assert not (target / "spreadsheets" / "quarterly-report.csv").exists()

    plan_path = write_plan(plan)
    assert plan_path == root / "organization-plan.json"
    assert json.loads(plan_path.read_text(encoding="utf-8"))["actions"][0]["source"] == (
        "incoming/Quarterly Report.csv"
    )


def test_collision_is_reported_and_apply_does_not_overwrite(tmp_path: Path) -> None:
    root, source, _ = make_project(tmp_path)
    first = source / "Client Report.csv"
    second = source / "client-report.csv"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    plan = build_plan(root)

    assert [action.status for action in plan.actions] == ["planned", "conflict"]
    journal_path = apply_plan(plan)
    destination = root / "working" / "spreadsheets" / "client-report.csv"
    assert destination.read_text(encoding="utf-8") == "first"
    assert second.is_file()
    assert json.loads(journal_path.read_text(encoding="utf-8"))["entries"]


def test_existing_destination_is_a_conflict_and_is_not_overwritten(tmp_path: Path) -> None:
    root, source, target = make_project(tmp_path)
    destination = target / "spreadsheets" / "report.csv"
    destination.parent.mkdir()
    destination.write_text("keep", encoding="utf-8")
    original = source / "report.csv"
    original.write_text("replace me", encoding="utf-8")

    plan = build_plan(root)

    assert plan.actions[0].status == "conflict"
    assert plan.actions[0].reason == "destination name already exists"
    apply_plan(plan)
    assert original.read_text(encoding="utf-8") == "replace me"
    assert destination.read_text(encoding="utf-8") == "keep"


def test_interrupted_organizer_move_keeps_source_and_writes_no_journal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, source, _ = make_project(tmp_path)
    original = source / "Notes.md"
    original.write_text("keep me", encoding="utf-8")

    def interrupted_move(*_: object) -> None:
        raise OSError("simulated interrupted move")

    monkeypatch.setattr("file_organizer.os.rename", interrupted_move)

    with pytest.raises(OSError, match="interrupted move"):
        apply_plan(build_plan(root))

    assert original.read_text(encoding="utf-8") == "keep me"
    assert not (root / "working" / "documents" / "notes.md").exists()
    assert not (root / "organization-journal.json").exists()


def test_quarantine_moves_only_conflicts_without_deleting_them(tmp_path: Path) -> None:
    root, source, _ = make_project(tmp_path)
    (source / "Plan.csv").write_text("first", encoding="utf-8")
    conflict = source / "plan.csv"
    conflict.write_text("second", encoding="utf-8")

    plan = build_plan(root)
    journal_path = quarantine_conflicts(plan)

    assert not conflict.exists()
    quarantine_files = list((root / "quarantine").rglob("plan.csv"))
    assert len(quarantine_files) == 1
    assert quarantine_files[0].read_text(encoding="utf-8") == "second"
    assert json.loads(journal_path.read_text(encoding="utf-8"))["entries"][0][
        "operation"
    ] == "quarantine"


def test_rollback_restores_applied_file_and_checks_hash(tmp_path: Path) -> None:
    root, source, _ = make_project(tmp_path)
    original = source / "Notes.md"
    original.write_text("keep me", encoding="utf-8")

    plan = build_plan(root)
    journal_path = apply_plan(plan)
    destination = root / "working" / "documents" / "notes.md"
    assert destination.is_file()
    assert not original.exists()

    assert rollback_journal(root, journal_path) == 1
    assert original.read_text(encoding="utf-8") == "keep me"
    assert not destination.exists()


def test_rollback_rejects_changed_destination(tmp_path: Path) -> None:
    root, source, _ = make_project(tmp_path)
    (source / "Notes.md").write_text("original", encoding="utf-8")

    journal_path = apply_plan(build_plan(root))
    destination = root / "working" / "documents" / "notes.md"
    destination.write_text("changed", encoding="utf-8")

    with pytest.raises(ValueError, match="hash changed"):
        rollback_journal(root, journal_path)


def test_plan_rejects_unsafe_source_directory(tmp_path: Path) -> None:
    root, _, _ = make_project(tmp_path)

    with pytest.raises(ValueError, match="single safe path components"):
        build_plan(root, source_dir="../outside")


def test_plan_rejects_unsafe_target_directory(tmp_path: Path) -> None:
    root, _, _ = make_project(tmp_path)

    with pytest.raises(ValueError, match="single safe path components"):
        build_plan(root, target_dir="../outside")


def test_plan_rejects_symlinked_approved_root(tmp_path: Path) -> None:
    root, _, _ = make_project(tmp_path)
    alias = tmp_path / "project-alias"
    alias.symlink_to(root, target_is_directory=True)

    with pytest.raises(ValueError, match="must not be a symlink"):
        build_plan(alias)


def test_plan_rejects_missing_source_directory(tmp_path: Path) -> None:
    root, source, _ = make_project(tmp_path)
    source.rmdir()

    with pytest.raises(NotADirectoryError, match="Source directory"):
        build_plan(root)


def test_plan_marks_source_as_conflict_when_target_is_same_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, source, _ = make_project(tmp_path)
    (source / "notes.md").write_text("notes", encoding="utf-8")
    monkeypatch.setattr(
        "file_organizer.destination_for",
        lambda current_root, target_dir, record: current_root / "incoming" / record.name,
    )

    plan = build_plan(root)

    assert plan.actions[0].status == "conflict"
    assert plan.actions[0].reason == "source already has the destination path"


def test_move_rejects_existing_symlink_destination(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("source", encoding="utf-8")
    destination.symlink_to(source)

    with pytest.raises(FileExistsError, match="Destination already exists"):
        move_without_overwrite(source, destination)

    assert source.read_text(encoding="utf-8") == "source"


def test_render_plan_includes_action_details(tmp_path: Path) -> None:
    root, source, _ = make_project(tmp_path)
    source_file = source / "notes.md"
    source_file.write_text("notes", encoding="utf-8")

    rendered = render_plan(build_plan(root))

    assert "1 action(s)" in rendered
    assert "[planned] incoming/notes.md" in rendered


def test_load_journal_rejects_non_list_entries(tmp_path: Path) -> None:
    journal = tmp_path / "invalid.json"
    journal.write_text('{"entries": {}}', encoding="utf-8")

    with pytest.raises(ValueError, match="entries list"):
        load_journal(journal)


def test_rollback_rejects_missing_journal_target(tmp_path: Path) -> None:
    root, _, _ = make_project(tmp_path)
    journal = write_journal(
        root,
        [JournalEntry("incoming/missing.md", "working/documents/missing.md", "", "move")],
    )

    with pytest.raises(FileNotFoundError, match="Journal target is missing"):
        rollback_journal(root, journal)


def test_rollback_rejects_existing_original_source(tmp_path: Path) -> None:
    root, source, _ = make_project(tmp_path)
    original = source / "notes.md"
    original.write_text("original", encoding="utf-8")
    journal = apply_plan(build_plan(root))
    destination = root / "working" / "documents" / "notes.md"
    original.write_text("already restored", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Destination already exists"):
        rollback_journal(root, journal)

    assert destination.read_text(encoding="utf-8") == "original"


def test_organization_plan_response_model_can_render_conflict() -> None:
    action = OrganizationAction(
        source="incoming/report.csv",
        destination="working/spreadsheets/report.csv",
        status="conflict",
        reason="destination name already exists",
    )
    plan = OrganizationPlan("/tmp/project", "2026-01-01T00:00:00+00:00", (action,))

    assert "[conflict]" in render_plan(plan)
