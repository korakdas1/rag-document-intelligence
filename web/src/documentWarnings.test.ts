import { describe, expect, it } from "vitest";
import { formatDocumentWarning } from "./documentWarnings";

describe("formatDocumentWarning", () => {
  it("labels persisted parser codes without inventing new ones", () => {
    expect(formatDocumentWarning("page_1_has_xobjects_not_extracted_as_text")).toBe(
      "Page 1 has images or graphics that were not extracted as text.",
    );
    expect(formatDocumentWarning("unclosed_code_fence")).toBe(
      "A Markdown code fence was not closed.",
    );
    expect(formatDocumentWarning("some_future_code")).toBe("some_future_code");
  });
});
