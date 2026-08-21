from __future__ import annotations

import json
from pathlib import Path

import pytest

from file_converter import (
    ConversionDestinationExistsError,
    ConversionError,
    UnsafeConversionPathError,
    build_conversion_request,
    convert_file,
)


def make_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "project"
    incoming = root / "incoming"
    output = root / "output"
    incoming.mkdir(parents=True)
    output.mkdir()
    return root, incoming, output


def test_csv_json_and_json_csv_conversion(tmp_path: Path) -> None:
    root, incoming, output = make_project(tmp_path)
    csv_source = incoming / "records.csv"
    csv_source.write_text("name,total\nalpha,3\nbeta,4\n", encoding="utf-8")

    json_result = convert_file(root, csv_source, output / "records.json")
    assert json_result.destination_relative == Path("output/records.json")
    assert json.loads((output / "records.json").read_text(encoding="utf-8")) == [
        {"name": "alpha", "total": "3"},
        {"name": "beta", "total": "4"},
    ]

    csv_result = convert_file(root, output / "records.json", output / "round-trip.csv")
    assert csv_result.bytes_written > 0
    assert (output / "round-trip.csv").read_text(encoding="utf-8") == (
        "name,total\nalpha,3\nbeta,4\n"
    )


def test_markdown_to_text_and_text_to_markdown_preserve_content(tmp_path: Path) -> None:
    root, incoming, output = make_project(tmp_path)
    markdown = incoming / "notes.md"
    markdown.write_text("# Heading\n\n- **important** [link](https://example.test)\n", encoding="utf-8")

    convert_file(root, markdown, output / "notes.txt")
    assert (output / "notes.txt").read_text(encoding="utf-8") == (
        "Heading\n\nimportant link\n"
    )

    convert_file(root, output / "notes.txt", output / "notes-round-trip.md")
    assert (output / "notes-round-trip.md").read_text(encoding="utf-8") == (
        "Heading\n\nimportant link\n"
    )


def test_png_to_jpg_conversion_preserves_original(tmp_path: Path) -> None:
    image = pytest.importorskip("PIL.Image")
    root, incoming, output = make_project(tmp_path)
    source = incoming / "sample.png"
    image.new("RGBA", (2, 2), (10, 20, 30, 255)).save(source, format="PNG")

    result = convert_file(root, source, output / "sample.jpg")

    assert result.destination_format == "jpg"
    assert source.is_file()
    with image.open(output / "sample.jpg") as converted:
        assert converted.format == "JPEG"
        assert converted.size == (2, 2)


def test_invalid_json_does_not_create_output_or_change_source(tmp_path: Path) -> None:
    root, incoming, output = make_project(tmp_path)
    source = incoming / "broken.json"
    source.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ConversionError, match="malformed"):
        convert_file(root, source, output / "broken.csv")

    assert source.read_text(encoding="utf-8") == "{not-json"
    assert not (output / "broken.csv").exists()


def test_empty_csv_is_rejected_without_creating_output(tmp_path: Path) -> None:
    root, incoming, output = make_project(tmp_path)
    source = incoming / "empty.csv"
    source.touch()

    with pytest.raises(ConversionError, match="header row"):
        convert_file(root, source, output / "empty.json")

    assert source.stat().st_size == 0
    assert not (output / "empty.json").exists()


def test_empty_json_is_rejected_without_creating_output(tmp_path: Path) -> None:
    root, incoming, output = make_project(tmp_path)
    source = incoming / "empty.json"
    source.touch()

    with pytest.raises(ConversionError, match="malformed"):
        convert_file(root, source, output / "empty.csv")

    assert source.stat().st_size == 0
    assert not (output / "empty.csv").exists()


def test_empty_markdown_and_text_are_valid_empty_outputs(tmp_path: Path) -> None:
    root, incoming, output = make_project(tmp_path)
    markdown = incoming / "empty.md"
    text = incoming / "empty.txt"
    markdown.touch()
    text.touch()

    convert_file(root, markdown, output / "empty.txt")
    convert_file(root, text, output / "empty.md")

    assert (output / "empty.txt").read_bytes() == b""
    assert (output / "empty.md").read_bytes() == b""


def test_invalid_utf8_is_rejected_without_creating_output(tmp_path: Path) -> None:
    root, incoming, output = make_project(tmp_path)
    source = incoming / "invalid.md"
    source.write_bytes(b"\xff\xfe\xfd")

    with pytest.raises(ConversionError, match="UTF-8"):
        convert_file(root, source, output / "invalid.txt")

    assert source.read_bytes() == b"\xff\xfe\xfd"
    assert not (output / "invalid.txt").exists()


def test_interrupted_output_write_cleans_temporary_file_and_preserves_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, incoming, output = make_project(tmp_path)
    source = incoming / "records.csv"
    source.write_text("name\nalpha\n", encoding="utf-8")

    def interrupted_link(*_: object) -> None:
        raise OSError("simulated interrupted output")

    monkeypatch.setattr("file_converter.os.link", interrupted_link)

    with pytest.raises(ConversionError, match="written safely"):
        convert_file(root, source, output / "records.json")

    assert source.read_text(encoding="utf-8") == "name\nalpha\n"
    assert not (output / "records.json").exists()
    assert list(output.glob(".conversion-*")) == []


def test_conversion_rejects_existing_destination_and_path_escape(tmp_path: Path) -> None:
    root, incoming, output = make_project(tmp_path)
    source = incoming / "records.csv"
    source.write_text("name\nalpha\n", encoding="utf-8")
    existing = output / "records.json"
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(ConversionDestinationExistsError):
        convert_file(root, source, existing)
    assert existing.read_text(encoding="utf-8") == "keep"

    with pytest.raises(UnsafeConversionPathError):
        build_conversion_request(root, source, "../outside.json")
