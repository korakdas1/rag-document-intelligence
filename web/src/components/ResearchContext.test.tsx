import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { documentScope } from "../documentScope";
import { ResearchContext } from "./ResearchContext";

const base = {
  id: "scope-context",
  scope: documentScope(true, []),
  libraryCount: 4,
  availableCount: 4,
  saving: false,
  error: null,
  loading: false,
  onRetry: vi.fn(),
};

describe("ResearchContext", () => {
  it("presents the next-question ALL scope without a noisy saved state", () => {
    render(<ResearchContext {...base} />);
    expect(screen.getByLabelText("Next question document scope"))
      .toHaveTextContent("Next question·All documents· 4 in library");
    expect(screen.queryByText(/Saved/)).not.toBeInTheDocument();
  });

  it("shows saving, missing-document, and loading states honestly", () => {
    const { rerender } = render(<ResearchContext {...base} saving />);
    expect(screen.getByRole("status")).toHaveTextContent("Saving selection…");
    rerender(<ResearchContext {...base} scope={documentScope(false, ["a", "b", "missing"])}
      availableCount={2} libraryCount={2} />);
    expect(screen.getByText("2 available of 3 selected")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1 selected document is unavailable.");
    rerender(<ResearchContext {...base} loading />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading research…");
    expect(screen.queryByText("All documents")).not.toBeInTheDocument();
  });

  it("exposes a concise failure and retries the current scope", async () => {
    const onRetry = vi.fn();
    render(<ResearchContext {...base} error="Could not save document selection." onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Selection not saved. Could not save document selection.",
    );
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry saving" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
