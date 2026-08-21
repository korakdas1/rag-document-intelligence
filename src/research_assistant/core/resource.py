"""Classify local resource exhaustion without exposing framework dumps."""

from __future__ import annotations

RESOURCE_EXHAUSTED_CODE = "resource_exhausted"

RESOURCE_EXHAUSTED_MESSAGE = (
    "Could not index this document: available model memory was insufficient. "
    "Try again after other processing finishes or free system/GPU memory."
)

GENERIC_RESOURCE_MESSAGE = (
    "Could not index this document because a local processing resource was unavailable."
)


def looks_like_resource_exhaustion(exc: object) -> bool:
    raw = str(exc).lower()
    if not raw.strip():
        return False
    if "out of memory" in raw or "pytorch allocator" in raw:
        return True
    if "cannot allocate memory" in raw or "std::bad_alloc" in raw:
        return True
    if "cuda" in raw and any(
        token in raw for token in ("memory", "allocator", "malloc", "oom")
    ):
        return True
    return False


def public_resource_message(filename: str | None = None) -> str:
    name = (filename or "").strip()
    if not name:
        return RESOURCE_EXHAUSTED_MESSAGE
    return (
        f"Could not index {name}: available model memory was insufficient. "
        "Try again after other processing finishes or free system/GPU memory."
    )


def sanitize_public_error(message: str, *, filename: str | None = None) -> str:
    if looks_like_resource_exhaustion(message):
        return public_resource_message(filename)
    return message
