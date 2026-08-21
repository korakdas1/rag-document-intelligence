from pathlib import Path

import pytest

from research_assistant.api.upload import sanitize_filename, unique_destination
from research_assistant.core.errors import FileValidationError, UnsupportedFileTypeError


def test_sanitize_strips_directories() -> None:
    assert sanitize_filename("../../notes.md") == "notes.md"
    assert sanitize_filename("C:\\\\Windows\\\\notes.txt") == "notes.txt"


def test_sanitize_rejects_unsupported_and_empty() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        sanitize_filename("payload.exe")
    with pytest.raises(FileValidationError):
        sanitize_filename("..")
    with pytest.raises(FileValidationError):
        sanitize_filename("")


def test_unique_destination_avoids_overwrite(tmp_path: Path) -> None:
    first = unique_destination(tmp_path, "paper.md")
    first.write_text("a", encoding="utf-8")
    second = unique_destination(tmp_path, "paper.md")
    assert second.name == "paper__2.md"
    assert second.parent == tmp_path.resolve()


def test_sanitize_absolute_and_nested_separators() -> None:
    assert sanitize_filename("..\\..\\Windows\\notes.md") == "notes.md"
    assert sanitize_filename("/var/tmp/notes.txt") == "notes.txt"
