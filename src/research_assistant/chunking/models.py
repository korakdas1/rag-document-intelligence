"""Retrieval unit produced by a Chunker. No embedding fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_assistant.chunking.identity import (
    approx_token_count,
    chunk_id_for,
    sha256_text,
)


@dataclass(frozen=True)
class Chunk:
    # --- identity ---
    chunk_id: str
    document_id: str
    chunker_id: str
    position: int
    # --- payload ---
    text: str
    content_hash: str
    char_count: int
    approx_token_count: int
    # --- locators ---
    source_block_start: int
    source_block_end: int
    page_start: int | None = None
    page_end: int | None = None
    section_path: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "chunker_id": self.chunker_id,
            "position": self.position,
            "text": self.text,
            "content_hash": self.content_hash,
            "char_count": self.char_count,
            "approx_token_count": self.approx_token_count,
            "source_block_start": self.source_block_start,
            "source_block_end": self.source_block_end,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section_path": list(self.section_path),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Chunk:
        return cls(
            chunk_id=str(data["chunk_id"]),
            document_id=str(data["document_id"]),
            chunker_id=str(data["chunker_id"]),
            position=int(data["position"]),
            text=str(data["text"]),
            content_hash=str(data["content_hash"]),
            char_count=int(data["char_count"]),
            approx_token_count=int(data["approx_token_count"]),
            source_block_start=int(data["source_block_start"]),
            source_block_end=int(data["source_block_end"]),
            page_start=data.get("page_start"),
            page_end=data.get("page_end"),
            section_path=tuple(data.get("section_path") or ()),
            warnings=tuple(data.get("warnings") or ()),
        )


def build_chunk(
    *,
    document_id: str,
    chunker_id: str,
    position: int,
    text: str,
    source_block_start: int,
    source_block_end: int,
    page_start: int | None,
    page_end: int | None,
    section_path: tuple[str, ...],
    warnings: tuple[str, ...] = (),
) -> Chunk:
    digest = sha256_text(text)
    return Chunk(
        chunk_id=chunk_id_for(
            document_id=document_id,
            chunker_id=chunker_id,
            source_block_start=source_block_start,
            source_block_end=source_block_end,
            position=position,
            content_hash=digest,
        ),
        document_id=document_id,
        chunker_id=chunker_id,
        position=position,
        text=text,
        content_hash=digest,
        char_count=len(text),
        approx_token_count=approx_token_count(len(text)),
        source_block_start=source_block_start,
        source_block_end=source_block_end,
        page_start=page_start,
        page_end=page_end,
        section_path=section_path,
        warnings=warnings,
    )
