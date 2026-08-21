"""Safe local upload helpers. Does not parse or index."""

from __future__ import annotations

import re
from pathlib import Path

from research_assistant.core.errors import FileValidationError, UnsupportedFileTypeError

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown"}
_GENERIC_CONTENT_TYPES = {
    "",
    "application/octet-stream",
    "binary/octet-stream",
}
_CONTENT_TYPES_BY_SUFFIX = {
    ".pdf": {"application/pdf", "application/x-pdf"},
    ".txt": {"text/plain", "text/txt"},
    ".md": {"text/markdown", "text/x-markdown", "text/plain"},
    ".markdown": {"text/markdown", "text/x-markdown", "text/plain"},
}
_UNSAFE = re.compile(r"[^\w.\- ]+", re.UNICODE)
_MAX_NAME = 180


def sanitize_filename(name: str) -> str:
    raw = (name or "").replace("\\", "/")
    base = Path(raw).name
    if not base or base in {".", ".."}:
        raise FileValidationError("Filename is missing.", code="invalid_file")
    if base.startswith("."):
        raise FileValidationError("Hidden filenames are not allowed.", code="invalid_file")
    safe = _UNSAFE.sub("_", base).strip(" .")
    if not safe or safe in {".", ".."}:
        raise FileValidationError("Filename is invalid.", code="invalid_file")
    suffix = Path(safe).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UnsupportedFileTypeError(
            f"Unsupported file type (suffix {suffix or '(none)'})."
        )
    stem = Path(safe).stem[:_MAX_NAME]
    if not stem:
        raise FileValidationError("Filename is invalid.", code="invalid_file")
    return stem + suffix


def normalize_content_type(content_type: str | None) -> str:
    raw = (content_type or "").split(";", 1)[0].strip().lower()
    return raw


def validate_upload_content_type(filename: str, content_type: str | None) -> None:
    """Extension is authoritative. MIME is a compatibility check, never trusted alone."""
    suffix = Path(filename).suffix.lower()
    media = normalize_content_type(content_type)
    if media in _GENERIC_CONTENT_TYPES:
        return
    allowed = _CONTENT_TYPES_BY_SUFFIX.get(suffix, set())
    if media not in allowed:
        raise UnsupportedFileTypeError(
            "Upload content type does not match a supported document format."
        )


def unique_destination(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    resolved_dir = directory.expanduser().resolve()
    candidate = (resolved_dir / filename).resolve()
    if candidate.parent != resolved_dir:
        raise FileValidationError("Refusing path traversal in upload.", code="invalid_file")
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    for index in range(2, 1000):
        alt = (resolved_dir / f"{stem}__{index}{suffix}").resolve()
        if alt.parent != resolved_dir:
            raise FileValidationError(
                "Refusing path traversal in upload.", code="invalid_file"
            )
        if not alt.exists():
            return alt
    raise FileValidationError("Could not allocate a unique upload path.", code="invalid_file")
