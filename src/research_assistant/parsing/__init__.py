"""Format-specific document parsers."""

from research_assistant.parsing.markdown import MarkdownParser
from research_assistant.parsing.models import ParsedDocument, TextBlock
from research_assistant.parsing.pdf import PdfParser
from research_assistant.parsing.plaintext import PlainTextParser
from research_assistant.parsing.protocol import DocumentParser, ParseInput
from research_assistant.parsing.registry import ParserRegistry, default_parsers

__all__ = [
    "DocumentParser",
    "MarkdownParser",
    "ParseInput",
    "ParsedDocument",
    "ParserRegistry",
    "PdfParser",
    "PlainTextParser",
    "TextBlock",
    "default_parsers",
]
