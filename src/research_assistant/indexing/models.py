"""Index metadata and vector payloads. No backend types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_assistant.storage.records import IndexMetadata

__all__ = ["IndexMetadata", "VectorHit", "VectorPayload", "VectorRecord"]

_SECTION_SEP = "\x1f"


@dataclass(frozen=True)
class VectorPayload:
    chunk_id: str
    document_id: str
    chunker_id: str
    position: int
    content_hash: str
    page_start: int | None
    page_end: int | None
    section_path: tuple[str, ...]
    filename: str
    char_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "chunker_id": self.chunker_id,
            "position": self.position,
            "content_hash": self.content_hash,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section_path": list(self.section_path),
            "section_prefixes": _section_prefix_keys(self.section_path),
            "filename": self.filename,
            "char_count": self.char_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VectorPayload:
        return cls(
            chunk_id=str(data["chunk_id"]),
            document_id=str(data["document_id"]),
            chunker_id=str(data["chunker_id"]),
            position=int(data["position"]),
            content_hash=str(data["content_hash"]),
            page_start=data.get("page_start"),
            page_end=data.get("page_end"),
            section_path=tuple(data.get("section_path") or ()),
            filename=str(data.get("filename") or ""),
            char_count=int(data.get("char_count") or 0),
        )


@dataclass(frozen=True)
class VectorRecord:
    chunk_id: str
    vector: list[float]
    payload: VectorPayload


@dataclass(frozen=True)
class VectorHit:
    chunk_id: str
    score: float
    payload: VectorPayload


def _section_prefix_keys(path: tuple[str, ...]) -> list[str]:
    keys: list[str] = []
    parts: list[str] = []
    for part in path:
        parts.append(part)
        keys.append(_SECTION_SEP.join(parts))
    return keys
