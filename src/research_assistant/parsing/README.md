# parsing

Format-specific extractors behind `DocumentParser`.

Includes `PlainTextParser`, `MarkdownParser`, `PdfParser` (pypdf), `ParserRegistry`, and `ParsedDocument` / `TextBlock`.

Downstream code should consume blocks, not `full_text()`, when splitting passages.
