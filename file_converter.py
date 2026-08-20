"""Safety foundation for controlled file conversions.

This module deliberately handles validation and conversion policy first. The
actual format handlers can use :class:`ConversionRequest` after the source,
destination, and format pair have passed these checks.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import tempfile
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

    raw = value.suffix if isinstance(value, Path) else (Path(str(value)).suffix or str(value))
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


@dataclass(frozen=True)
class ConversionResult:
    """Details about one successfully written conversion output."""

    root: Path
    source: Path
    destination: Path
    source_format: str
    destination_format: str
    bytes_written: int

    @property
    def destination_relative(self) -> Path:
        """Return the output path relative to the approved root."""

        return safe_relative_path(self.root, self.destination)


def _read_utf8(source: Path) -> str:
    """Read a text source with a clear conversion error for invalid UTF-8."""

    try:
        return source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ConversionError("Text conversion sources must be valid UTF-8.") from exc


def _csv_to_json(source: Path) -> bytes:
    """Convert a UTF-8 CSV document to an indented JSON list of objects."""

    reader = csv.DictReader(io.StringIO(_read_utf8(source), newline=""))
    fieldnames = reader.fieldnames
    if not fieldnames or any(not name for name in fieldnames):
        raise ConversionError("CSV input must contain a non-empty header row.")
    if len(set(fieldnames)) != len(fieldnames):
        raise ConversionError("CSV input must not contain duplicate column names.")

    rows: list[dict[str, str]] = []
    for row in reader:
        if None in row:
            raise ConversionError("CSV input contains a row with too many columns.")
        rows.append({name: row.get(name, "") or "" for name in fieldnames})
    return (json.dumps(rows, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _json_to_csv(source: Path) -> bytes:
    """Convert a JSON list of flat objects to a UTF-8 CSV document."""

    try:
        payload = json.loads(_read_utf8(source))
    except json.JSONDecodeError as exc:
        raise ConversionError("JSON input is malformed.") from exc
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise ConversionError("JSON input must be a list of objects.")

    fieldnames: list[str] = []
    for row in payload:
        for name, value in row.items():
            if not isinstance(name, str) or not name:
                raise ConversionError("JSON object keys must be non-empty strings.")
            if isinstance(value, (dict, list)):
                raise ConversionError("JSON values for CSV conversion must be scalar.")
            if name not in fieldnames:
                fieldnames.append(name)

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    if fieldnames:
        writer.writeheader()
        writer.writerows(payload)
    return stream.getvalue().encode("utf-8")


_MARKDOWN_LINK_RE = re.compile(r"!?\[([^]]*)\]\([^)]*\)")
_MARKDOWN_DECORATION_RE = re.compile(r"(```?|\*\*|__|\*|_)")


def _markdown_to_text(source: Path) -> bytes:
    """Remove common Markdown presentation markers while preserving content."""

    lines: list[str] = []
    for original_line in _read_utf8(source).splitlines():
        line = original_line.strip()
        if line.startswith("```"):
            continue
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^>\s?", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        line = _MARKDOWN_LINK_RE.sub(r"\1", line)
        line = _MARKDOWN_DECORATION_RE.sub("", line)
        lines.append(line)
    text = "\n".join(lines).rstrip()
    return ((text + "\n") if text else "").encode("utf-8")


def _text_to_markdown(source: Path) -> bytes:
    """Write valid UTF-8 plain text as Markdown without changing its content."""

    text = _read_utf8(source)
    if text and not text.endswith("\n"):
        text += "\n"
    return text.encode("utf-8")


def _image_to_bytes(request: ConversionRequest) -> bytes:
    """Convert one approved image pair through Pillow when available."""

    try:
        from PIL import Image
    except ImportError as exc:
        raise ConversionError("Image conversion requires the Pillow dependency.") from exc

    output = io.BytesIO()
    try:
        with Image.open(request.source) as image:
            image.load()
            if request.destination_format == "jpg" and image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            image.save(output, format="JPEG" if request.destination_format == "jpg" else "PNG")
    except (OSError, ValueError) as exc:
        raise ConversionError("Image input could not be decoded or converted.") from exc
    return output.getvalue()


def _render_conversion(request: ConversionRequest) -> bytes:
    """Render conversion output in memory before creating its destination."""

    pair = (request.source_format, request.destination_format)
    if pair == ("csv", "json"):
        return _csv_to_json(request.source)
    if pair == ("json", "csv"):
        return _json_to_csv(request.source)
    if pair == ("md", "txt"):
        return _markdown_to_text(request.source)
    if pair == ("txt", "md"):
        return _text_to_markdown(request.source)
    if request.kind == "image":
        return _image_to_bytes(request)
    raise UnsupportedFormatError(
        f"Unsupported conversion: {request.source_format} to {request.destination_format}."
    )


def _write_without_overwrite(destination: Path, content: bytes) -> int:
    """Write bytes through a temporary file and atomically link without overwrite."""

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=".conversion-",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary_path, destination)
        except FileExistsError as exc:
            raise ConversionDestinationExistsError(
                f"Conversion destination already exists: {destination}"
            ) from exc
        return len(content)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def convert_request(request: ConversionRequest) -> ConversionResult:
    """Convert a validated request without overwriting or deleting originals."""

    try:
        content = _render_conversion(request)
        bytes_written = _write_without_overwrite(request.destination, content)
    except ConversionError:
        raise
    except OSError as exc:
        raise ConversionError("Conversion output could not be written safely.") from exc
    return ConversionResult(
        root=request.root,
        source=request.source,
        destination=request.destination,
        source_format=request.source_format,
        destination_format=request.destination_format,
        bytes_written=bytes_written,
    )


def convert_file(
    approved_root: Path | str,
    source: Path | str,
    destination: Path | str,
) -> ConversionResult:
    """Validate paths and formats, then perform one controlled conversion."""

    return convert_request(build_conversion_request(approved_root, source, destination))


__all__ = [
    "APPROVED_CONVERSION_PAIRS",
    "ConversionDestinationExistsError",
    "ConversionError",
    "ConversionKind",
    "ConversionRequest",
    "ConversionResult",
    "IMAGE_FORMATS",
    "SUPPORTED_FORMATS",
    "TEXT_FORMATS",
    "UnsafeConversionPathError",
    "UnsupportedFormatError",
    "build_conversion_request",
    "convert_file",
    "convert_request",
    "format_kind",
    "normalize_format",
    "validate_conversion_paths",
]
