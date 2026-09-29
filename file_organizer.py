"""Safe dry-run file organiser."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import stat
import tempfile
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
INTERNAL_JOURNAL_DIRECTORY = ".ccl-journals"
INTERNAL_PLAN_DIRECTORY = ".ccl-organization"
MAX_ORGANIZATION_ACTIONS = 1000

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
        if len(actions) >= MAX_ORGANIZATION_ACTIONS:
            raise ValueError("Organization plan exceeds the action limit.")
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
    """Return a portable plan representation without host filesystem paths."""

    return {
        "actions": [asdict(action) for action in plan.actions],
        "root": ".",
    }


def plan_digest(plan: OrganizationPlan) -> str:
    """Bind an apply request to the previewed actions and file checksums."""

    actions = [asdict(action) for action in plan.actions]
    return hashlib.sha256(json.dumps(actions, sort_keys=True).encode("utf-8")).hexdigest()


def write_plan(plan: OrganizationPlan, output: Path | None = None) -> Path:
    """Write an immutable plan without replacing project files."""

    root = resolve_approved_root(plan.root)
    digest = plan_digest(plan)
    payload = json.dumps(
        {**plan_dict(plan), "digest": digest},
        indent=2,
        sort_keys=True,
    ).encode("utf-8") + b"\n"

    internal_plans = root / INTERNAL_PLAN_DIRECTORY / "plans"
    current = root
    for part in (INTERNAL_PLAN_DIRECTORY, "plans"):
        current = current / part
        if current.is_symlink():
            raise ValueError("Organization plan directories must not be symlinks.")
        current.mkdir(parents=True, exist_ok=True, mode=0o750)
        if current.is_symlink() or not current.is_dir():
            raise ValueError("Organization plan directory is not safe.")

    if output is None:
        preferred_path = internal_plans / f"{digest}.json"
    else:
        candidate = Path(os.path.abspath(Path(output).expanduser()))
        try:
            relative = candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Plan output must stay inside the approved root.") from exc
        if not relative.parts:
            raise ValueError("Plan output must name a file inside the approved root.")
        current = root
        for part in relative.parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise ValueError("Plan output directories must not be symlinks.")
            current.mkdir(parents=True, exist_ok=True, mode=0o750)
        preferred_path = candidate

    candidates = [preferred_path]
    if preferred_path != internal_plans / f"{digest}.json":
        candidates.append(internal_plans / f"{digest}.json")
    candidates.extend(
        internal_plans / f"{digest}-{secrets.token_hex(12)}.json"
        for _ in range(3)
    )
    for destination in candidates:
        if _create_plan_file(destination, payload):
            return destination
        if _plan_file_matches(destination, payload):
            return destination
    raise FileExistsError("A unique organization plan path could not be allocated.")


def _plan_file_matches(path: Path, payload: bytes) -> bool:
    """Compare an existing regular plan without following symbolic links."""

    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return False
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            return False
        return stream.read(len(payload) + 1) == payload


def _create_plan_file(path: Path, payload: bytes) -> bool:
    """Atomically publish plan bytes only when the destination is unused."""

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=".plan-",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
            return True
        except FileExistsError:
            return False
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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
    candidate = output or root / INTERNAL_JOURNAL_DIRECTORY / f"organization-{secrets.token_hex(16)}.json"
    if candidate.is_symlink():
        raise ValueError("Journal destination must not be a symlink.")
    destination = candidate.resolve(strict=False)
    safe_relative_path(root, destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entries": [asdict(entry) for entry in entries],
    }
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, indent=2) + "\n")
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
    journal_path = journal_path or root / INTERNAL_JOURNAL_DIRECTORY / f"organization-{secrets.token_hex(16)}.json"
    if journal_path.exists() or journal_path.is_symlink():
        raise FileExistsError("Journal destination already exists.")
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
    journal_path = journal_path or root / INTERNAL_JOURNAL_DIRECTORY / f"quarantine-{secrets.token_hex(16)}.json"
    if journal_path.exists() or journal_path.is_symlink():
        raise FileExistsError("Journal destination already exists.")
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
    if not isinstance(payload, dict):
        raise ValueError("Journal must be a JSON object.")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Journal must contain an entries list.")
    try:
        return [JournalEntry(**entry) for entry in entries]
    except (TypeError, KeyError) as exc:
        raise ValueError("Journal contains an invalid entry.") from exc


def rollback_journal(
    approved_root: Path | str,
    journal_path: Path,
    source_dir: str = DEFAULT_SOURCE_DIR,
    target_dir: str = DEFAULT_TARGET_DIR,
) -> int:
    """Restore journaled files after verifying their recorded hashes."""

    root = resolve_approved_root(approved_root)
    approved_child(root, source_dir)
    approved_child(root, target_dir)
    restored = 0
    entries = load_journal(journal_path)
    if len(entries) > MAX_ORGANIZATION_ACTIONS:
        raise ValueError("Journal has too many entries.")
    pending_moves: list[tuple[Path, Path]] = []
    seen_sources: set[str] = set()
    seen_destinations: set[str] = set()
    for entry in reversed(entries):
        if not all(
            isinstance(value, str)
            for value in (entry.source, entry.destination, entry.sha256, entry.operation)
        ):
            raise ValueError("Journal entry fields must be strings.")
        if entry.source in seen_sources or entry.destination in seen_destinations:
            raise ValueError("Journal contains duplicate paths.")
        seen_sources.add(entry.source)
        seen_destinations.add(entry.destination)
        if not re.fullmatch(r"[0-9a-f]{64}", entry.sha256):
            raise ValueError("Journal entry has no valid checksum.")
        source = Path(entry.source)
        destination = Path(entry.destination)
        if ".." in source.parts or ".." in destination.parts:
            raise ValueError("Journal paths must not contain parent segments.")
        if source.parts[:1] != (source_dir,):
            raise ValueError("Journal source must be in the incoming directory.")
        if entry.operation == "move":
            category = FILE_CATEGORIES.get(source.suffix.lower(), "other")
            expected = Path(target_dir) / category / normalize_filename(source.name)
            if destination != expected:
                raise ValueError("Journal move must target the expected working directory.")
        elif entry.operation == "quarantine":
            if (
                destination.parts[:1] != (DEFAULT_QUARANTINE_DIR,)
                or len(destination.parts) < 4
                or destination.parts[2:] != source.parts
            ):
                raise ValueError("Journal quarantine target is invalid.")
        else:
            raise ValueError("Journal operation is invalid.")
        current = root / entry.destination
        original = root / entry.source
        safe_relative_path(root, current)
        safe_relative_path(root, original)
        if not current.is_file():
            raise FileNotFoundError(f"Journal target is missing: {entry.destination}")
        if sha256_file(current) != entry.sha256:
            raise ValueError(f"Journal target hash changed: {entry.destination}")
        if original.exists() or original.is_symlink():
            raise FileExistsError(f"Destination already exists: {original}")
        pending_moves.append((current, original))
    for current, original in pending_moves:
        move_without_overwrite(current, original)
        restored += 1
    return restored


def build_parser() -> argparse.ArgumentParser:
    """Build the safe organiser command-line interface."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Approved project root")
    parser.add_argument("--source", default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--target", default=DEFAULT_TARGET_DIR)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--quarantine-conflicts", action="store_true")
    parser.add_argument("--rollback", type=Path)
    return parser


def main() -> int:
    """Preview, apply, quarantine, or roll back an organisation plan."""

    parser = build_parser()
    args = parser.parse_args()
    try:
        root = resolve_approved_root(args.root)
        if args.rollback is not None:
            restored = rollback_journal(root, args.rollback, args.source, args.target)
            print(f"Rolled back {restored} operation(s).")
            return 0
        plan = build_plan(root, args.source, args.target)
        plan_path = write_plan(plan, args.plan)
        print(render_plan(plan))
        print(f"Plan written to {plan_path.relative_to(root)}")
        if args.quarantine_conflicts and not args.apply:
            parser.error("--quarantine-conflicts requires --apply.")
        if args.apply:
            journal = apply_plan(plan, args.journal)
            print(f"Journal written to {journal.relative_to(root)}")
            if args.quarantine_conflicts:
                quarantine_journal = quarantine_conflicts(plan)
                print(f"Conflicts quarantined in {quarantine_journal.relative_to(root)}")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ActionStatus",
    "FileRecord",
    "JournalEntry",
    "OrganizationAction",
    "OrganizationPlan",
    "apply_plan",
    "approved_child",
    "build_parser",
    "build_plan",
    "category_for",
    "destination_for",
    "load_journal",
    "main",
    "move_without_overwrite",
    "normalize_filename",
    "plan_dict",
    "quarantine_conflicts",
    "quarantine_destination",
    "render_plan",
    "rollback_journal",
    "write_journal",
    "write_plan",
]
