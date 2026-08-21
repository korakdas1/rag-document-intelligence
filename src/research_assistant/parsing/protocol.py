"""Parser protocol and parse input."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from research_assistant.core.types import ContentType
from research_assistant.parsing.models import ParsedDocument


@dataclass(frozen=True)
class ParseInput:
    document_id: str
    path: Path
    data: bytes
    content_type: ContentType


class DocumentParser(Protocol):
    """Format-specific extractor. Implementations must not leak library types."""

    @property
    def parser_id(self) -> str: ...

    def supports(self, content_type: ContentType) -> bool: ...

    def parse(self, source: ParseInput) -> ParsedDocument: ...
