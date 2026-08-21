"""Typed retrieval filters. Same semantics for dense, lexical, and hybrid."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_assistant.chunking.models import Chunk
from research_assistant.core.errors import RetrievalError

SECTION_PREFIX_SEP = "\x1f"


@dataclass(frozen=True)
class RetrievalFilter:
    """AND across fields; OR within multi-value fields.

    * ``document_ids`` — exact ``document_id`` membership
    * ``filenames`` — exact basename membership
    * ``page`` — interval overlap against ``page_start``/``page_end``
    * ``section_prefix`` — section path must start with this tuple (ancestor match)
    """

    document_ids: tuple[str, ...] = ()
    filenames: tuple[str, ...] = ()
    page: int | None = None
    section_prefix: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if any(not item.strip() for item in self.document_ids):
            raise RetrievalError(
                "document_ids must not contain empty values",
                code="invalid_filter",
            )
        if any(not item.strip() for item in self.filenames):
            raise RetrievalError(
                "filenames must not contain empty values",
                code="invalid_filter",
            )
        if self.page is not None and self.page < 1:
            raise RetrievalError("page must be >= 1", code="invalid_filter")

    @property
    def active(self) -> bool:
        return bool(
            self.document_ids or self.filenames or self.page is not None or self.section_prefix
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_ids": list(self.document_ids),
            "filenames": list(self.filenames),
            "page": self.page,
            "section_prefix": list(self.section_prefix),
        }


def section_prefix_keys(path: tuple[str, ...]) -> list[str]:
    keys: list[str] = []
    parts: list[str] = []
    for part in path:
        parts.append(part)
        keys.append(SECTION_PREFIX_SEP.join(parts))
    return keys


def chunk_matches_filter(
    chunk: Chunk,
    filt: RetrievalFilter | None,
    *,
    filename: str = "",
) -> bool:
    if filt is None or not filt.active:
        return True
    if filt.document_ids and chunk.document_id not in filt.document_ids:
        return False
    if filt.filenames and filename not in filt.filenames:
        return False
    if filt.page is not None:
        if chunk.page_start is None or chunk.page_end is None:
            return False
        if not (chunk.page_start <= filt.page <= chunk.page_end):
            return False
    if filt.section_prefix:
        path = chunk.section_path
        prefix = filt.section_prefix
        if len(path) < len(prefix) or path[: len(prefix)] != prefix:
            return False
    return True
