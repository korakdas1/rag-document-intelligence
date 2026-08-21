"""Parsed document representation used by the chunking pipeline.

This is not a universal document AST. Blocks carry the locators chunking
and citations will need: order, kind, page, heading path, and text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_assistant.core.types import BlockKind


@dataclass(frozen=True)
class TextBlock:
    position: int
    kind: BlockKind
    text: str
    page: int | None = None
    heading_level: int | None = None
    section_path: tuple[str, ...] = ()

    @property
    def block_id(self) -> str:
        return f"b{self.position:04d}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "kind": self.kind.value,
            "text": self.text,
            "page": self.page,
            "heading_level": self.heading_level,
            "section_path": list(self.section_path),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextBlock:
        return cls(
            position=int(data["position"]),
            kind=BlockKind(data["kind"]),
            text=str(data["text"]),
            page=data.get("page"),
            heading_level=data.get("heading_level"),
            section_path=tuple(data.get("section_path") or ()),
        )


@dataclass(frozen=True)
class ParsedDocument:
    document_id: str
    blocks: tuple[TextBlock, ...]
    parser_id: str
    warnings: tuple[str, ...] = ()
    page_count: int | None = None

    def full_text(self) -> str:
        """Debug/inspect helper. Chunking should iterate `blocks`, not this."""
        return "\n\n".join(block.text for block in self.blocks if block.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "parser_id": self.parser_id,
            "warnings": list(self.warnings),
            "page_count": self.page_count,
            "blocks": [block.to_dict() for block in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParsedDocument:
        blocks = tuple(TextBlock.from_dict(item) for item in data.get("blocks") or [])
        return cls(
            document_id=str(data["document_id"]),
            blocks=blocks,
            parser_id=str(data["parser_id"]),
            warnings=tuple(data.get("warnings") or ()),
            page_count=data.get("page_count"),
        )
