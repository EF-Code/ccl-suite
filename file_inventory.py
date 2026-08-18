"""Day 2 file inventory scanner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import subprocess
from dataclasses import asdict, dataclass, fields
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
    )


def scan_files(approved_root: Path | str) -> list[FileRecord]:
    """Scan all regular files below the approved root."""
    root = resolve_approved_root(approved_root)
    return [inventory_file(root, path) for path in iter_regular_files(root)]


def _manifest_paths(
    root: Path,
    json_path: Path | None,
    csv_path: Path | None,
) -> tuple[Path, Path]:
    """Resolve manifest paths and keep both outputs below the root."""

    for candidate in (json_path, csv_path):
        if candidate is not None and candidate.is_symlink():
            raise ValueError("Manifest output must not be a symlink.")
    json_output = (json_path or root / DEFAULT_JSON_NAME).resolve(strict=False)
    csv_output = (csv_path or root / DEFAULT_CSV_NAME).resolve(strict=False)
    if json_output == csv_output:
        raise ValueError("JSON and CSV manifest paths must be different.")
    for output in (json_output, csv_output):
        if not output.is_relative_to(root):
            raise ValueError("Manifest output must stay inside the approved root.")
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    return json_output, csv_output


def write_manifests(
    approved_root: Path | str,
    records: Iterable[FileRecord],
    json_path: Path | None = None,
    csv_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write deterministic JSON and CSV manifests below the approved root."""

    root = resolve_approved_root(approved_root)
    json_output, csv_output = _manifest_paths(root, json_path, csv_path)
    rows = [asdict(record) for record in records]
    json_output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    fieldnames = [field.name for field in fields(FileRecord)]
    with csv_output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return json_output, csv_output


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface for the inventory scanner."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
        help="Approved root to scan (default: CCL_PROJECT_ROOT or ./projects)",
    )
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--csv", dest="csv_path", type=Path)
    return parser


def main() -> int:
    """Scan the approved root and write both manifest formats."""

    parser = build_parser()
    args = parser.parse_args()
    try:
        root = resolve_approved_root(args.root)
        records = scan_files(root)
        json_path, csv_path = write_manifests(
            root, records, args.json_path, args.csv_path
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))

    print(f"Scanned {len(records)} files.")
    print(f"JSON manifest: {json_path.relative_to(root)}")
    print(f"CSV manifest: {csv_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_PROJECT_ROOT",
    "FileRecord",
    "build_parser",
    "detect_mime_type",
    "extension_mime_match",
    "inventory_file",
    "iter_regular_files",
    "main",
    "resolve_approved_root",
    "safe_relative_path",
    "scan_files",
    "sha256_file",
    "write_manifests",
]
