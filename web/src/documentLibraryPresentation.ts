import type { DocumentSummary } from "./api/types";

export type DocumentLibraryCounts = Readonly<{
  total: number;
  ready: number;
  processing: number;
  attention: number;
}>;

export function documentLibraryCounts(documents: readonly DocumentSummary[]): DocumentLibraryCounts {
  let ready = 0;
  let processing = 0;
  let attention = 0;

  for (const document of documents) {
    if (document.source_available === false || document.status === "failed") {
      attention += 1;
    } else if (document.status === "ready") {
      ready += 1;
    } else {
      processing += 1;
    }
  }

  return { total: documents.length, ready, processing, attention };
}

export function documentTotalLabel(total: number): string {
  if (total === 0) return "Empty";
  return `${total} document${total === 1 ? "" : "s"}`;
}

export function documentStatusSummary(counts: DocumentLibraryCounts): string | null {
  if (counts.total === 0) return null;
  const parts: string[] = [];
  if (counts.ready > 0) parts.push(`${counts.ready} ready`);
  if (counts.processing > 0) parts.push(`${counts.processing} processing`);
  if (counts.attention > 0) parts.push(`${counts.attention} need${counts.attention === 1 ? "s" : ""} attention`);
  return parts.join(" · ");
}

export function filenameOccurrences(documents: readonly DocumentSummary[]): ReadonlyMap<string, number> {
  const counts = new Map<string, number>();
  for (const document of documents) {
    counts.set(document.filename, (counts.get(document.filename) ?? 0) + 1);
  }
  return counts;
}
