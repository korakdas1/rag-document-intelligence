"""Local filesystem validation before parse."""

from __future__ import annotations

from pathlib import Path

from research_assistant.core.errors import FileValidationError


def validate_ingest_path(path: Path, *, max_file_bytes: int) -> Path:
    if not path.exists():
        raise FileValidationError(f"File not found: {path}", code="not_found")
    if path.is_dir():
        raise FileValidationError(
            f"Expected a file, got a directory: {path}", code="is_directory"
        )
    if not path.is_file():
        raise FileValidationError(f"Not a regular file: {path}", code="not_a_file")
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise FileValidationError(
            f"Unable to resolve path {path}: {exc}", code="unreadable"
        ) from exc
    try:
        size = resolved.stat().st_size
    except OSError as exc:
        raise FileValidationError(
            f"Unable to stat file {resolved}: {exc}", code="unreadable"
        ) from exc
    if size > max_file_bytes:
        raise FileValidationError(
            f"File exceeds max size ({size} > {max_file_bytes} bytes): {resolved}",
            code="too_large",
        )
    return resolved
