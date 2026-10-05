import { describe, expect, it } from "vitest";
import type { DocumentSummary } from "./api/types";
import {
  documentLibraryCounts,
  documentStatusSummary,
  documentTotalLabel,
  filenameOccurrences,
} from "./documentLibraryPresentation";

function doc(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    document_id: "doc-1",
    filename: "notes.md",
    content_type: "text/markdown",
    status: "ready",
    page_count: 1,
    chunk_count: 1,
    byte_size: 12,
    warning_count: 0,
    ingested_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    parse_status: "parsed",
    error_message: null,
    ...overrides,
  };
}

describe("documentLibraryPresentation", () => {
  it("uses truthful empty and document totals", () => {
    expect(documentTotalLabel(0)).toBe("Empty");
    expect(documentTotalLabel(1)).toBe("1 document");
    expect(documentTotalLabel(12)).toBe("12 documents");
  });

  it("counts ready, processing, and attention without treating warnings as failure", () => {
    const counts = documentLibraryCounts([
      doc({ warning_count: 2 }),
      doc({ document_id: "parsed", status: "parsed" }),
      doc({ document_id: "chunked", status: "chunked" }),
      doc({ document_id: "failed", status: "failed" }),
      doc({ document_id: "missing", source_available: false }),
    ]);
    expect(counts).toEqual({ total: 5, ready: 1, processing: 2, attention: 2 });
    expect(documentStatusSummary(counts)).toBe("1 ready · 2 processing · 2 need attention");
  });

  it("precomputes duplicate filename counts once", () => {
    const counts = filenameOccurrences([
      doc(),
      doc({ document_id: "doc-2" }),
      doc({ document_id: "doc-3", filename: "unique.pdf" }),
    ]);
    expect(counts.get("notes.md")).toBe(2);
    expect(counts.get("unique.pdf")).toBe(1);
  });
});
