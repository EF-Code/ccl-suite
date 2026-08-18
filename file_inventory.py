"""Day 2 file inventory scanner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_PROJECT_ROOT = Path(os.getenv("CCL_PROJECT_ROOT", "projects"))
DEFAULT_JSON_NAME = "manifest.json"
DEFAULT_CSV_NAME = "manifest.csv"
MIME_COMMAND = ("file", "--brief", "--mime-type")
@dataclass(frozen=True)
class FileRecord:
    """One manifest row for a regular file."""

    relative_path: str
    name: str
    extension: str
    mime_type: str
    size_bytes: int
    modified_at: str
    sha256: str
    extension_mime_match: bool | None

def resolve_approved_root(root: Path | str) -> Path:
    """Resolve one existing, non-symlink approved root."""

    candidate = Path(root).expanduser()
    if candidate.is_symlink():
        raise ValueError("Approved root must not be a symlink.")
    resolved = candidate.resolve(strict=False)
    if not resolved.is_dir():
        raise NotADirectoryError(f"Approved root is not a directory: {resolved}")
    if resolved.stat().st_mode & 0o002:
        raise PermissionError("Approved root must not be world-writable.")
    return resolved
def safe_relative_path(root: Path, path: Path) -> Path:
    """Return a path inside the approved root."""
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path escapes the approved root.") from exc

def iter_regular_files(root: Path) -> Iterable[Path]:
    """Yield regular, non-symlink files below root."""
    for current, directories, filenames in os.walk(root, followlinks=False):
        directories[:] = sorted(
            name for name in directories
            if not (Path(current) / name).is_symlink()
        )
        for name in sorted(filenames):
            path = Path(current) / name
            if path.is_symlink() or not path.is_file():
                continue
            safe_relative_path(root, path)
            yield path

def sha256_file(path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Hash a file in bounded chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()

def detect_mime_type(path: Path) -> str:
    """Detect MIME from content, not the filename extension."""
    result = subprocess.run(
        [*MIME_COMMAND, "--", str(path)],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    mime_type = result.stdout.strip()
    if result.returncode != 0 or not mime_type:
        return "application/octet-stream"
    return mime_type

def extension_mime_match(path: Path, mime_type: str) -> bool | None:
    """Compare independent extension and content checks."""
    expected, _ = mimetypes.guess_type(path.name)
    if expected is None:
        return None
    return expected == mime_type
def inventory_file(root: Path, path: Path) -> FileRecord:
    """Build one manifest record for a regular file."""
    relative = safe_relative_path(root, path)
    details = path.stat()
    mime_type = detect_mime_type(path)
    return FileRecord(
        relative_path=relative.as_posix(),
        name=path.name,
        extension=path.suffix.lower(),
        mime_type=mime_type,
        size_bytes=details.st_size,
        modified_at=datetime.fromtimestamp(
            details.st_mtime, tz=timezone.utc
        ).isoformat(),
        sha256=sha256_file(path),
        extension_mime_match=extension_mime_match(path, mime_type),
