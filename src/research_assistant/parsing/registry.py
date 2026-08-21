"""Parser dispatch. First matching parser wins."""

from __future__ import annotations

from collections.abc import Sequence

from research_assistant.core.errors import UnsupportedFileTypeError
from research_assistant.core.types import ContentType
from research_assistant.parsing.markdown import MarkdownParser
from research_assistant.parsing.pdf import PdfParser
from research_assistant.parsing.plaintext import PlainTextParser
from research_assistant.parsing.protocol import DocumentParser, ParseInput
from research_assistant.parsing.models import ParsedDocument


class ParserRegistry:
    def __init__(self, parsers: Sequence[DocumentParser] | None = None) -> None:
        self._parsers = list(parsers) if parsers is not None else default_parsers()

    def get(self, content_type: ContentType) -> DocumentParser:
        for parser in self._parsers:
            if parser.supports(content_type):
                return parser
        raise UnsupportedFileTypeError(
            f"No parser registered for content type {content_type}"
        )

    def parse(self, source: ParseInput) -> tuple[DocumentParser, ParsedDocument]:
        parser = self.get(source.content_type)
        return parser, parser.parse(source)


def default_parsers() -> list[DocumentParser]:
    return [PlainTextParser(), MarkdownParser(), PdfParser()]
