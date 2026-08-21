"""Helpers for building ParsedDocument fixtures without touching the filesystem."""

from __future__ import annotations

from research_assistant.core.types import BlockKind
from research_assistant.parsing.models import ParsedDocument, TextBlock


def block(
    position: int,
    text: str,
    *,
    kind: BlockKind = BlockKind.PARAGRAPH,
    page: int | None = None,
    heading_level: int | None = None,
    section_path: tuple[str, ...] = (),
) -> TextBlock:
    return TextBlock(
        position=position,
        kind=kind,
        text=text,
        page=page,
        heading_level=heading_level,
        section_path=section_path,
    )


def parsed(*blocks: TextBlock, document_id: str = "doc-test") -> ParsedDocument:
    return ParsedDocument(
        document_id=document_id,
        blocks=tuple(blocks),
        parser_id="test.v1",
    )
