"""Safe dry-run file organiser."""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from file_inventory import (
    FileRecord,
    inventory_file,
    iter_regular_files,
    resolve_approved_root,
    safe_relative_path,
    sha256_file,
)

DEFAULT_SOURCE_DIR = "incoming"
DEFAULT_TARGET_DIR = "working"
DEFAULT_QUARANTINE_DIR = "quarantine"
DEFAULT_JOURNAL_NAME = "organization-journal.json"
DEFAULT_PLAN_NAME = "organization-plan.json"

ActionStatus = Literal["planned", "conflict", "applied", "quarantined", "rolled_back"]
FILE_CATEGORIES = {
    ".csv": "spreadsheets",
    ".json": "data",
    ".md": "documents",
    ".pdf": "documents",
    ".png": "images",
    ".jpg": "images",
    ".jpeg": "images",
    ".gif": "images",
    ".zip": "archives",
}


@dataclass(frozen=True)
class OrganizationAction:
    """One planned source-to-destination operation."""

    source: str
    destination: str
    status: ActionStatus = "planned"
    reason: str = ""
    sha256: str | None = None


@dataclass(frozen=True)
class OrganizationPlan:
    """Immutable dry-run plan for one approved root."""

    root: str
    created_at: str
    actions: tuple[OrganizationAction, ...]


def category_for(record: FileRecord) -> str:
    """Return the deterministic destination category for one file."""

    return FILE_CATEGORIES.get(record.extension, "other")


def normalize_filename(name: str) -> str:
    """Normalize one basename without allowing path components."""

    if Path(name).name != name or name in {".", ".."}:
        raise ValueError("File names must not contain path components.")
    original = Path(name)
    extension = original.suffix.lower()
    stem = unicodedata.normalize("NFKD", original.stem)
    stem = stem.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    if not normalized:
        raise ValueError("File name must contain letters or numbers.")
    return f"{normalized}{extension}"


def approved_child(root: Path, name: str) -> Path:
    """Resolve a named child directory while preserving the root boundary."""

    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("Directory names must be single safe path components.")
    child = root / name
    safe_relative_path(root, child)
    return child


def destination_for(root: Path, target_dir: str, record: FileRecord) -> Path:
    """Compute one deterministic destination below the approved root."""

    target = approved_child(root, target_dir)
    category = approved_child(target, category_for(record))
    destination = category / normalize_filename(record.name)
    safe_relative_path(root, destination)
    return destination


def build_plan(
    approved_root: Path | str,
    source_dir: str = DEFAULT_SOURCE_DIR,
    target_dir: str = DEFAULT_TARGET_DIR,
) -> OrganizationPlan:
    """Build a no-mutation plan for organising files from source_dir."""

    root = resolve_approved_root(approved_root)
    source = approved_child(root, source_dir)
    approved_child(root, target_dir)
    if not source.is_dir():
        raise NotADirectoryError(f"Source directory is not available: {source}")
    actions: list[OrganizationAction] = []
    destinations: set[str] = set()
    for path in iter_regular_files(source):
        record = inventory_file(source, path)
        destination = destination_for(root, target_dir, record)
        source_rel = safe_relative_path(root, path).as_posix()
        destination_rel = safe_relative_path(root, destination).as_posix()
        status: ActionStatus = "planned"
        reason = "ready"
        if source_rel == destination_rel:
            status, reason = "conflict", "source already has the destination path"
        elif destination_rel in destinations or destination.exists():
            status, reason = "conflict", "destination name already exists"
        destinations.add(destination_rel)
        actions.append(
            OrganizationAction(
                source=source_rel,
                destination=destination_rel,
                status=status,
                reason=reason,
                sha256=record.sha256,
            )
        )
    return OrganizationPlan(
        root=root.as_posix(),
        created_at=datetime.now(timezone.utc).isoformat(),
        actions=tuple(actions),
    )


def plan_dict(plan: OrganizationPlan) -> dict[str, object]:
    """Return a JSON-ready representation of a plan."""

    return asdict(plan)


def write_plan(plan: OrganizationPlan, output: Path | None = None) -> Path:
    """Write a dry-run plan inside its approved root."""

    root = Path(plan.root)
    destination = (output or root / DEFAULT_PLAN_NAME).resolve(strict=False)
    safe_relative_path(root, destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    destination.write_text(json.dumps(plan_dict(plan), indent=2) + "\n", encoding="utf-8")
    return destination


def render_plan(plan: OrganizationPlan) -> str:
    """Render a human-readable dry-run preview without changing files."""

    lines = [f"Plan for {plan.root}: {len(plan.actions)} action(s)"]
    for action in plan.actions:
        lines.append(f"[{action.status}] {action.source} -> {action.destination} ({action.reason})")
    return "\n".join(lines)


@dataclass(frozen=True)
class JournalEntry:
    """One reversible filesystem operation."""

    source: str
    destination: str
    sha256: str
    operation: Literal["move", "quarantine"]


def write_journal(
    approved_root: Path | str,
    entries: list[JournalEntry],
    output: Path | None = None,
) -> Path:
    """Persist applied operations inside the approved root."""

    root = resolve_approved_root(approved_root)
    destination = (output or root / DEFAULT_JOURNAL_NAME).resolve(strict=False)
    safe_relative_path(root, destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entries": [asdict(entry) for entry in entries],
    }
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def move_without_overwrite(source: Path, destination: Path) -> None:
    """Move one file only when its destination is still absent."""

    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    os.rename(source, destination)


def quarantine_destination(root: Path, source_relative: str) -> Path:
    """Create a unique, confined destination for a conflicted file."""

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    quarantine = approved_child(root, DEFAULT_QUARANTINE_DIR)
    destination = quarantine / stamp / Path(source_relative)
    safe_relative_path(root, destination)
    return destination


def apply_plan(
    plan: OrganizationPlan,
    journal_path: Path | None = None,
) -> Path:
    """Apply only conflict-free actions and persist a rollback journal."""

    root = resolve_approved_root(plan.root)
    entries: list[JournalEntry] = []
    for action in plan.actions:
        if action.status != "planned":
            continue
        source = root / action.source
        destination = root / action.destination
        safe_relative_path(root, source)
        safe_relative_path(root, destination)
        move_without_overwrite(source, destination)
        entries.append(
            JournalEntry(action.source, action.destination, action.sha256 or "", "move")
        )
    return write_journal(root, entries, journal_path)


def quarantine_conflicts(
    plan: OrganizationPlan,
    journal_path: Path | None = None,
) -> Path:
    """Move conflict actions to quarantine without deleting originals."""

    root = resolve_approved_root(plan.root)
    entries: list[JournalEntry] = []
    for action in plan.actions:
        if action.status != "conflict":
            continue
        source = root / action.source
        destination = quarantine_destination(root, action.source)
        safe_relative_path(root, source)
        move_without_overwrite(source, destination)
        entries.append(
            JournalEntry(action.source, safe_relative_path(root, destination).as_posix(), action.sha256 or "", "quarantine")
        )
    return write_journal(root, entries, journal_path)


def load_journal(path: Path) -> list[JournalEntry]:
    """Load and validate journal entries from JSON."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Journal must contain an entries list.")
    return [JournalEntry(**entry) for entry in entries]


def rollback_journal(approved_root: Path | str, journal_path: Path) -> int:
    """Restore journaled files after verifying their recorded hashes."""

    root = resolve_approved_root(approved_root)
    restored = 0
    for entry in reversed(load_journal(journal_path)):
        current = root / entry.destination
        original = root / entry.source
        safe_relative_path(root, current)
        safe_relative_path(root, original)
        if not current.is_file():
            raise FileNotFoundError(f"Journal target is missing: {entry.destination}")
        if entry.sha256 and sha256_file(current) != entry.sha256:
            raise ValueError(f"Journal target hash changed: {entry.destination}")
        move_without_overwrite(current, original)
        restored += 1
    return restored
