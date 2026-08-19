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
