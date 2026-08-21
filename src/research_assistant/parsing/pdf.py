"""PDF parser backed by pypdf."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from research_assistant.core.errors import ParseError
from research_assistant.core.types import BlockKind, ContentType
from research_assistant.parsing.models import ParsedDocument, TextBlock
from research_assistant.parsing.normalize import split_paragraphs
from research_assistant.parsing.protocol import ParseInput


class PdfParser:
    parser_id = "pdf.pypdf.v1"

    def supports(self, content_type: ContentType) -> bool:
        return content_type is ContentType.PDF

    def parse(self, source: ParseInput) -> ParsedDocument:
        try:
            reader = PdfReader(BytesIO(source.data), strict=False)
        except PdfReadError as exc:
            raise ParseError(f"Unable to read PDF {source.path}: {exc}") from exc
        except Exception as exc:  # pypdf can raise several parse errors
            raise ParseError(f"Unable to read PDF {source.path}: {exc}") from exc

        if reader.is_encrypted:
            raise ParseError(f"Encrypted PDFs are not supported: {source.path}")

        blocks: list[TextBlock] = []
        warnings: list[str] = []
        page_count = len(reader.pages)

        for page_number, page in enumerate(reader.pages, start=1):
            try:
                extracted = page.extract_text() or ""
            except Exception as exc:
                warnings.append(f"page_{page_number}_extract_failed:{exc.__class__.__name__}")
                extracted = ""

            xobjects = _xobject_names(page)
            paragraphs = split_paragraphs(extracted)
            if not paragraphs:
                if xobjects:
                    warnings.append(
                        f"page_{page_number}_no_extractable_text_with_xobjects"
                    )
                else:
                    warnings.append(f"page_{page_number}_empty")
                continue

            if xobjects:
                warnings.append(
                    f"page_{page_number}_has_xobjects_not_extracted_as_text"
                )

            for paragraph in paragraphs:
                blocks.append(
                    TextBlock(
                        position=len(blocks),
                        kind=BlockKind.PARAGRAPH,
                        text=paragraph,
                        page=page_number,
                    )
                )

        if page_count == 0:
            warnings.append("pdf_has_no_pages")
        if not blocks:
            warnings.append("no_extractable_text")
            warnings.append("ocr_not_attempted")

        return ParsedDocument(
            document_id=source.document_id,
            blocks=tuple(blocks),
            parser_id=self.parser_id,
            warnings=tuple(warnings),
            page_count=page_count,
        )


def _xobject_names(page: object) -> list[str]:
    try:
        resources = page.get("/Resources")  # type: ignore[attr-defined]
        if resources is None:
            return []
        resources = resources.get_object()
        xobject = resources.get("/XObject")
        if xobject is None:
            return []
        xobject = xobject.get_object()
        return [str(name) for name in xobject.keys()]
    except Exception:
        return []
