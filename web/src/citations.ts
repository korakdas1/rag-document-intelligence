export type AnswerSegment =
  | { kind: "text"; text: string }
  | { kind: "citation"; citationId: string };

const CITATION = /(\[S\d+\])/g;

export function splitCitations(answer: string): AnswerSegment[] {
  if (!answer) {
    return [];
  }
  const parts = answer.split(CITATION);
  const segments: AnswerSegment[] = [];
  for (const part of parts) {
    if (!part) {
      continue;
    }
    const match = /^\[(S\d+)\]$/.exec(part);
    if (match) {
      segments.push({ kind: "citation", citationId: match[1] });
    } else {
      segments.push({ kind: "text", text: part });
    }
  }
  return segments;
}
