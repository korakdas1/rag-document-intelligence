import { describe, expect, it } from "vitest";
import { splitCitations } from "./citations";

describe("splitCitations", () => {
  it("keeps surrounding text and citation tokens", () => {
    const segments = splitCitations("Self-attention models token relationships [S1].");
    expect(segments).toEqual([
      { kind: "text", text: "Self-attention models token relationships " },
      { kind: "citation", citationId: "S1" },
      { kind: "text", text: "." },
    ]);
  });

  it("does not treat S99-like words as citations without brackets", () => {
    const segments = splitCitations("See source S1 in the notes.");
    expect(segments).toEqual([{ kind: "text", text: "See source S1 in the notes." }]);
  });
});
