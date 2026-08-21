import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { SourceView } from "../api/types";
import { SourcePanel } from "./SourcePanel";

const sources: SourceView[] = [
  {
    citation_id: "S1",
    filename: "a-very-long-research-paper-filename-that-should-not-overflow.md",
    document_id: "doc-1",
    page_start: 13,
    page_end: 13,
    section_path: ["Ending"],
    locator: "duplicate-filename-should-not-lead",
    text: "They marry in the final chapter.",
    truncated: false,
    cited_by_model: true,
  },
  {
    citation_id: "S2",
    filename: "notes.md",
    document_id: "doc-2",
    page_start: 2,
    page_end: 2,
    section_path: [],
    locator: "notes.md, p. 2",
    text: "A retrieved passage that was not cited.",
    truncated: false,
    cited_by_model: false,
  },
];

describe("SourcePanel", () => {
  it("distinguishes cited and retrieved sources without duplicating the locator filename", () => {
    render(
      <SourcePanel sources={sources} activeCitationId="S1" onSelect={vi.fn()} />,
    );
    expect(screen.getByText("Cited")).toBeInTheDocument();
    expect(screen.getByText("Retrieved")).toBeInTheDocument();
    expect(screen.getByText("Page 13 · Ending")).toBeInTheDocument();
    expect(screen.queryByText("duplicate-filename-should-not-lead")).not.toBeInTheDocument();
    expect(
      screen.getByTitle(
        "a-very-long-research-paper-filename-that-should-not-overflow.md",
      ),
    ).toBeInTheDocument();
    expect(document.getElementById("source-S1")).toHaveAttribute("aria-current", "true");
  });

  it("marks evidence from documents no longer in the library", () => {
    render(
      <SourcePanel
        sources={sources}
        activeCitationId={null}
        knownDocumentIds={new Set(["doc-1"])}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("Removed from library")).toBeInTheDocument();
  });

  it("notifies when a source card is selected", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<SourcePanel sources={sources} activeCitationId={null} onSelect={onSelect} />);
    await user.click(screen.getByRole("button", { name: /\[S2\]/ }));
    expect(onSelect).toHaveBeenCalledWith("S2");
  });
});
