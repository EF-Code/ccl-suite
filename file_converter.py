"""Safety foundation for controlled file conversions.

This module deliberately handles validation and conversion policy first. The
actual format handlers can use :class:`ConversionRequest` after the source,
destination, and format pair have passed these checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from file_inventory import resolve_approved_root, safe_relative_path

ConversionKind = Literal["text", "image"]

TEXT_FORMATS: Final[frozenset[str]] = frozenset({"csv", "json", "md", "txt"})
IMAGE_FORMATS: Final[frozenset[str]] = frozenset({"jpg", "png"})
SUPPORTED_FORMATS: Final[frozenset[str]] = TEXT_FORMATS | IMAGE_FORMATS
FORMAT_ALIASES: Final[dict[str, str]] = {
    "markdown": "md",
    "jpeg": "jpg",
}
APPROVED_CONVERSION_PAIRS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("csv", "json"),
        ("json", "csv"),
        ("md", "txt"),
        ("txt", "md"),
        ("jpg", "png"),
        ("png", "jpg"),
    }
)


class ConversionError(ValueError):
    """Base error for a conversion request that fails validation."""


class UnsupportedFormatError(ConversionError):
    """Raised when a format or conversion pair is not allow-listed."""


class UnsafeConversionPathError(ConversionError):
    """Raised when a conversion path is outside the approved root."""


class ConversionDestinationExistsError(ConversionError):
    """Raised instead of overwriting an existing destination file."""


@dataclass(frozen=True)
class ConversionRequest:
    """A validated request ready for a conversion handler."""

    root: Path
    source: Path
    destination: Path
    source_format: str
    destination_format: str
    kind: ConversionKind

    @property
    def source_relative(self) -> Path:
        """Return the source path relative to the approved root."""

        return safe_relative_path(self.root, self.source)

    @property
    def destination_relative(self) -> Path:
        """Return the destination path relative to the approved root."""

        return safe_relative_path(self.root, self.destination)


def normalize_format(value: str | Path) -> str:
    """Return a canonical allow-listed format name.

    Both extensions (``.jpeg``) and format names (``jpeg``) are accepted.
    ``jpeg`` and ``markdown`` are normalised to the canonical names ``jpg``
    and ``md``.
    """

    raw = value.suffix if isinstance(value, Path) else str(value)
    candidate = raw.lower().lstrip(".")
    canonical = FORMAT_ALIASES.get(candidate, candidate)
    if canonical not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(f"Unsupported conversion format: {candidate or '<empty>'}.")
    return canonical


def format_kind(format_name: str) -> ConversionKind:
    """Return the approved family for a canonical format name."""

    canonical = normalize_format(format_name)
    return "text" if canonical in TEXT_FORMATS else "image"


def _rooted_path(root: Path, candidate: Path | str) -> Path:
    """Interpret relative conversion paths below root."""

    path = Path(candidate).expanduser()
    return path if path.is_absolute() else root / path


def _validate_path(
    root: Path,
    candidate: Path | str,
    *,
    label: str,
    must_exist: bool,
) -> Path:
    """Resolve one source or destination while preserving the root boundary."""

    path = _rooted_path(root, candidate)
    if path.is_symlink():
        raise UnsafeConversionPathError(f"{label} must not be a symlink.")
    resolved = path.resolve(strict=False)
    try:
        safe_relative_path(root, resolved)
    except ValueError as exc:
        raise UnsafeConversionPathError(
            f"{label} must remain inside the approved project root."
        ) from exc
    if must_exist and not resolved.is_file():
        raise FileNotFoundError(f"Conversion source is not a regular file: {resolved}")
    return resolved


def validate_conversion_paths(
    approved_root: Path | str,
    source: Path | str,
    destination: Path | str,
) -> tuple[Path, Path, Path]:
    """Validate source and destination paths without modifying the filesystem."""

    root = resolve_approved_root(approved_root)
    source_path = _validate_path(root, source, label="Conversion source", must_exist=True)
    destination_path = _validate_path(
        root,
        destination,
        label="Conversion destination",
        must_exist=False,
    )
    if source_path == destination_path:
        raise UnsafeConversionPathError("Conversion source and destination must differ.")
    if destination_path.exists():
        raise ConversionDestinationExistsError(
            f"Conversion destination already exists: {destination_path}"
        )
    return root, source_path, destination_path


def build_conversion_request(
    approved_root: Path | str,
    source: Path | str,
    destination: Path | str,
) -> ConversionRequest:
    """Create a validated request for an approved conversion pair."""

    root, source_path, destination_path = validate_conversion_paths(
        approved_root, source, destination
    )
    source_format = normalize_format(source_path)
    destination_format = normalize_format(destination_path)
    pair = (source_format, destination_format)
    if pair not in APPROVED_CONVERSION_PAIRS:
        raise UnsupportedFormatError(
            f"Unsupported conversion: {source_format} to {destination_format}."
        )
    source_kind = format_kind(source_format)
    if source_kind != format_kind(destination_format):
        raise UnsupportedFormatError("Conversions cannot mix text and image formats.")
    return ConversionRequest(
        root=root,
        source=source_path,
        destination=destination_path,
        source_format=source_format,
        destination_format=destination_format,
        kind=source_kind,
    )


__all__ = [
    "APPROVED_CONVERSION_PAIRS",
    "ConversionDestinationExistsError",
    "ConversionError",
    "ConversionKind",
    "ConversionRequest",
    "IMAGE_FORMATS",
    "SUPPORTED_FORMATS",
    "TEXT_FORMATS",
    "UnsafeConversionPathError",
    "UnsupportedFormatError",
    "build_conversion_request",
    "format_kind",
    "normalize_format",
    "validate_conversion_paths",
]
