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

from file_inventory import FileRecord, resolve_approved_root, safe_relative_path

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
