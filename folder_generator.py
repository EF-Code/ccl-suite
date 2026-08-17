"""Create a safe, standard project-folder layout.

The generator accepts one approved root and never treats a project name as a
path.  It creates a new project only; it does not overwrite or delete an
existing project folder.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PROJECT_ROOT = Path(os.getenv("CCL_PROJECT_ROOT", "projects"))
PROJECT_NAME_MAX_LENGTH = 64
PROJECT_DIRECTORY_MODE = 0o750
PROJECT_SUBDIRECTORIES = ("incoming", "working", "output", "archive")
PROJECT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class ProjectFolders:
    """The paths created for one project."""

    name: str
    root: Path
    project: Path
    incoming: Path
    working: Path
    output: Path
    archive: Path

    @property
    def subdirectories(self) -> tuple[Path, ...]:
        """Return the standard child directories in their documented order."""

        return (self.incoming, self.working, self.output, self.archive)


def normalize_project_name(project_name: str) -> str:
    """Convert a display name to the company's lowercase kebab-case format.

    Path separators and dot segments are rejected instead of being silently
    interpreted as filesystem instructions.
    """

    if not isinstance(project_name, str):
        raise TypeError("Project name must be text.")

    value = project_name.strip()
    if not value:
        raise ValueError("Project name must not be empty.")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("Project name must not contain path separators or dot segments.")
    if any(ord(character) < 32 for character in value):
        raise ValueError("Project name must not contain control characters.")

    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value).strip("-").lower()
    if not normalized:
        raise ValueError("Project name must contain at least one letter or number.")
    if len(normalized) > PROJECT_NAME_MAX_LENGTH:
        raise ValueError(
            f"Project name must be at most {PROJECT_NAME_MAX_LENGTH} characters after normalization."
        )
    if PROJECT_NAME_PATTERN.fullmatch(normalized) is None:
        raise ValueError("Project name must use lowercase kebab-case.")
    return normalized


def _resolve_approved_root(approved_root: Path | str) -> Path:
    """Resolve and validate the configured filesystem boundary."""

    root_input = Path(approved_root).expanduser()
    if root_input.is_symlink():
        raise ValueError("Approved project root must not be a symlink.")

    root = root_input.resolve(strict=False)
    if root == root.parent:
        raise ValueError("The filesystem root is not an approved project location.")
    if root.exists() and not root.is_dir():
        raise NotADirectoryError(f"Approved project root is not a directory: {root}")
    if root.exists() and stat.S_IMODE(root.stat().st_mode) & stat.S_IWOTH:
        raise PermissionError("Approved project root must not be world-writable.")
    return root


def create_project_folder(
    project_name: str,
    approved_root: Path | str = DEFAULT_PROJECT_ROOT,
) -> ProjectFolders:
    """Create a standard project folder below ``approved_root``.

    The operation is deliberately create-only.  A collision raises
    ``FileExistsError`` and leaves the existing project untouched.
    """

    name = normalize_project_name(project_name)
    root = _resolve_approved_root(approved_root)
    project = root / name
    resolved_project = project.resolve(strict=False)
    if not resolved_project.is_relative_to(root):
        raise ValueError("Generated project path escapes the approved root.")
    if project.exists() or project.is_symlink():
        raise FileExistsError(f"Project already exists: {name}")

    root.mkdir(parents=True, exist_ok=True, mode=PROJECT_DIRECTORY_MODE)
    # Re-check after creation so a race cannot replace the approved root with
    # a world-writable directory between validation and the mkdir call.
    if stat.S_IMODE(root.stat().st_mode) & stat.S_IWOTH:
        raise PermissionError("Approved project root must not be world-writable.")

    created: list[Path] = []
    try:
        project.mkdir(mode=PROJECT_DIRECTORY_MODE)
        created.append(project)
        children = {child: project / child for child in PROJECT_SUBDIRECTORIES}
        for child in children.values():
            child.mkdir(mode=PROJECT_DIRECTORY_MODE)
            created.append(child)
    except Exception:
        for directory in reversed(created):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise

    return ProjectFolders(
        name=name,
        root=root,
        project=project,
        incoming=project / "incoming",
        working=project / "working",
        output=project / "output",
        archive=project / "archive",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Display name to normalize and create")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
        help="Approved project root (default: CCL_PROJECT_ROOT or ./projects)",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        folders = create_project_folder(args.name, args.root)
    except (OSError, TypeError, ValueError) as exc:
        _build_parser().error(str(exc))

    print(f"Created project: {folders.name}")
    for directory in folders.subdirectories:
        print(f"Created: {directory.relative_to(folders.root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_PROJECT_ROOT",
    "PROJECT_DIRECTORY_MODE",
    "PROJECT_NAME_MAX_LENGTH",
    "PROJECT_NAME_PATTERN",
    "PROJECT_SUBDIRECTORIES",
    "ProjectFolders",
    "create_project_folder",
    "normalize_project_name",
]
