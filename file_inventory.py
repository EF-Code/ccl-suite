"""Day 2 file inventory scanner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import secrets
import stat
import subprocess
import tempfile
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_PROJECT_ROOT = Path(os.getenv("CCL_PROJECT_ROOT", "projects"))
DEFAULT_JSON_NAME = ".ccl-inventory/manifest.json"
DEFAULT_CSV_NAME = ".ccl-inventory/manifest.csv"
INTERNAL_DIRECTORY_NAMES = frozenset(
    {".ccl-versions", ".ccl-journals", ".ccl-inventory", ".ccl-organization"}
)
INTERNAL_JOURNAL_NAMES = frozenset({"organization-journal.json", "quarantine-journal.json"})
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


def is_internal_write_path(relative_path: Path | str) -> bool:
    """Keep client-created files away from application-managed storage."""

    parts = Path(relative_path).parts
    return bool(parts) and (
        parts[0] in INTERNAL_DIRECTORY_NAMES
        or (len(parts) == 1 and parts[0] in INTERNAL_JOURNAL_NAMES)
    )


def iter_regular_files(root: Path) -> Iterable[Path]:
    """Yield regular, non-symlink files below root."""
    for current, directories, filenames in os.walk(root, followlinks=False):
        directories[:] = sorted(
            name for name in directories
            if name not in INTERNAL_DIRECTORY_NAMES
            and not (Path(current) / name).is_symlink()
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

    def resolve_output(candidate: Path | None, default_name: str) -> Path:
        raw_path = Path(candidate or root / default_name).expanduser()
        lexical_path = Path(os.path.abspath(raw_path))
        try:
            relative = lexical_path.relative_to(root)
        except ValueError as exc:
            raise ValueError("Manifest output must stay inside the approved root.") from exc
        if not relative.parts:
            raise ValueError("Manifest output must name a file inside the approved root.")
        if lexical_path.is_symlink():
            raise ValueError("Manifest output must not be a symlink.")

        current = root
        for part in relative.parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise ValueError("Manifest output directories must not be symlinks.")
            current.mkdir(parents=True, exist_ok=True, mode=0o750)
            if current.is_symlink() or not current.is_dir():
                raise ValueError("Manifest output directory is not safe.")

        output = lexical_path.resolve(strict=False)
        if not output.is_relative_to(root):
            raise ValueError("Manifest output must stay inside the approved root.")
        return output

    json_output = resolve_output(json_path, DEFAULT_JSON_NAME)
    csv_output = resolve_output(csv_path, DEFAULT_CSV_NAME)
    if json_output == csv_output:
        raise ValueError("JSON and CSV manifest paths must be different.")
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
    json_payload = (json.dumps(rows, indent=2) + "\n").encode("utf-8")

    fieldnames = [field.name for field in fields(FileRecord)]
    with tempfile.SpooledTemporaryFile(mode="w+t", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        stream.seek(0)
        csv_payload = stream.read().encode("utf-8")

    json_output = _publish_manifest_without_replacement(root, json_output, json_payload)
    csv_output = _publish_manifest_without_replacement(root, csv_output, csv_payload)
    return json_output, csv_output


def _manifest_matches(path: Path, payload: bytes) -> bool:
    """Check an existing regular manifest without following symbolic links."""

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return False
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            return False
        return stream.read(len(payload) + 1) == payload


def _create_manifest_exclusively(path: Path, payload: bytes) -> bool:
    """Atomically create one manifest only when its destination is unused."""

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=".manifest-",
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


def _publish_manifest_without_replacement(
    root: Path,
    preferred_path: Path,
    payload: bytes,
) -> Path:
    """Reuse identical output or publish under a unique internal path."""

    if _create_manifest_exclusively(preferred_path, payload):
        return preferred_path
    if _manifest_matches(preferred_path, payload):
        return preferred_path

    internal_directory = root / ".ccl-inventory"
    if internal_directory.is_symlink():
        raise ValueError("Manifest output directory must not be a symlink.")
    internal_directory.mkdir(parents=True, exist_ok=True, mode=0o750)
    if internal_directory.is_symlink() or not internal_directory.is_dir():
        raise ValueError("Manifest output directory is not safe.")

    digest = hashlib.sha256(payload).hexdigest()
    candidates = [
        internal_directory / f"{preferred_path.stem}-{digest}{preferred_path.suffix}"
    ]
    candidates.extend(
        internal_directory
        / f"{preferred_path.stem}-{secrets.token_hex(12)}{preferred_path.suffix}"
        for _ in range(3)
    )
    for candidate in candidates:
        if _create_manifest_exclusively(candidate, payload):
            return candidate
        if _manifest_matches(candidate, payload):
            return candidate
    raise FileExistsError("A unique manifest output path could not be allocated.")


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
    "INTERNAL_DIRECTORY_NAMES",
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
