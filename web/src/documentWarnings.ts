/** Labels for persisted parser/index warning codes. Does not invent new warnings. */

const PAGE_XOBJECTS = /^page_(\d+)_has_xobjects_not_extracted_as_text$/;
const PAGE_EMPTY = /^page_(\d+)_empty$/;
const PAGE_NO_TEXT_XOBJECTS = /^page_(\d+)_no_extractable_text_with_xobjects$/;
const PAGE_EXTRACT_FAILED = /^page_(\d+)_extract_failed:(.+)$/;
const SKIPPED_EMPTY = /^skipped_empty:(\d+)$/;
const VECTOR_PURGE = /^vector_purge_failed:(.+)$/;

const EXACT: Record<string, string> = {
  unclosed_code_fence: "A Markdown code fence was not closed.",
  empty_document: "The document contained no extractable text.",
  pdf_has_no_pages: "The PDF has no pages.",
  no_extractable_text: "No extractable text was found.",
  ocr_not_attempted: "OCR was not attempted.",
  crosses_sections: "A chunk crosses section boundaries.",
  crosses_pages: "A chunk crosses page boundaries.",
  partial_block: "A chunk includes a partial text block.",
  empty_after_join: "A section was empty after blocks were joined.",
};

export function formatDocumentWarning(code: string): string {
  const exact = EXACT[code];
  if (exact) {
    return exact;
  }
  let match = code.match(PAGE_XOBJECTS);
  if (match) {
    return `Page ${match[1]} has images or graphics that were not extracted as text.`;
  }
  match = code.match(PAGE_EMPTY);
  if (match) {
    return `Page ${match[1]} had no extractable text.`;
  }
  match = code.match(PAGE_NO_TEXT_XOBJECTS);
  if (match) {
    return `Page ${match[1]} had no extractable text (embedded images were present).`;
  }
  match = code.match(PAGE_EXTRACT_FAILED);
  if (match) {
    return `Page ${match[1]} text extraction failed (${match[2]}).`;
  }
  match = code.match(SKIPPED_EMPTY);
  if (match) {
    return `${match[1]} empty chunk(s) were skipped while indexing.`;
  }
  match = code.match(VECTOR_PURGE);
  if (match) {
    return `Previous indexed vectors could not be fully removed (${match[1]}).`;
  }
  return code;
}
