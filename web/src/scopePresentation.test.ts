import { describe, expect, it } from "vitest";
import { documentScope } from "./documentScope";
import { scopePresentation } from "./scopePresentation";

describe("scopePresentation", () => {
  it("labels ALL from canonical mode at any library count", () => {
    expect(scopePresentation(documentScope(true, []), 4, 4)).toEqual({
      label: "All documents", detail: "4 in library", warning: null,
    });
    expect(scopePresentation(documentScope(true, []), 0, 0)).toEqual({
      label: "All documents", detail: "Library empty", warning: null,
    });
  });

  it("keeps a fixed subset distinct even when it equals the current library", () => {
    expect(scopePresentation(documentScope(false, ["a", "b", "c", "d"]), 4, 4).label)
      .toBe("4 selected documents");
  });

  it("labels NONE explicitly", () => {
    expect(scopePresentation(documentScope(false, []), 4, 0).label)
      .toBe("No documents selected");
  });

  it("reports available and missing members of a saved subset", () => {
    expect(scopePresentation(documentScope(false, ["a", "b", "missing"]), 2, 2)).toEqual({
      label: "2 available of 3 selected",
      detail: null,
      warning: "1 selected document is unavailable.",
    });
    expect(scopePresentation(documentScope(false, ["a", "b", "x", "y"]), 2, 2).warning)
      .toBe("2 selected documents are unavailable.");
  });
});
