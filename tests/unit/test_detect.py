from pathlib import Path

import pytest

from research_assistant.core.errors import FileValidationError, UnsupportedFileTypeError
from research_assistant.core.types import ContentType
from research_assistant.ingestion.detect import detect_content_type


def test_detects_txt_by_extension(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes(b"hello")
    assert detect_content_type(path, b"hello") is ContentType.PLAIN_TEXT


def test_detects_markdown_by_extension(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    path.write_bytes(b"# hi")
    assert detect_content_type(path, b"# hi") is ContentType.MARKDOWN


def test_pdf_magic_wins_over_txt_extension(tmp_path: Path) -> None:
    path = tmp_path / "disguised.txt"
    header = b"%PDF-1.4"
    assert detect_content_type(path, header) is ContentType.PDF


def test_pdf_extension_without_magic_fails(tmp_path: Path) -> None:
    path = tmp_path / "fake.pdf"
    with pytest.raises(FileValidationError) as exc:
        detect_content_type(path, b"not a pdf")
    assert exc.value.code == "not_a_pdf"


def test_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "note.html"
    with pytest.raises(UnsupportedFileTypeError):
        detect_content_type(path, b"<html>")
