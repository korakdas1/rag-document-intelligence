"""Lightweight content-type detection. Magic for PDF; extension otherwise."""

from __future__ import annotations

from pathlib import Path

from research_assistant.core.errors import FileValidationError, UnsupportedFileTypeError
from research_assistant.core.types import ContentType

PDF_MAGIC = b"%PDF-"
_MARKDOWN_SUFFIXES = {".md", ".markdown"}
_TEXT_SUFFIXES = {".txt"}
_PDF_SUFFIXES = {".pdf"}


def detect_content_type(path: Path, header: bytes) -> ContentType:
    suffix = path.suffix.lower()
    stripped = header.lstrip(b"\r\n\t ")
    looks_like_pdf = stripped.startswith(PDF_MAGIC) or header.startswith(PDF_MAGIC)

    if looks_like_pdf:
        return ContentType.PDF

    if suffix in _PDF_SUFFIXES:
        raise FileValidationError(
            f"Extension is .pdf but the file does not start with PDF magic: {path}",
            code="not_a_pdf",
        )

    if suffix in _MARKDOWN_SUFFIXES:
        return ContentType.MARKDOWN
    if suffix in _TEXT_SUFFIXES:
        return ContentType.PLAIN_TEXT

    raise UnsupportedFileTypeError(
        f"Unsupported file type for {path.name} (suffix {suffix or '(none)'})"
    )
