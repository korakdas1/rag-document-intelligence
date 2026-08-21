import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { DocumentSummary } from "../api/types";
import { DocumentActions } from "./DocumentActions";

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

function Harness({
  document = doc(),
  onDetails = vi.fn(),
  onReindex = vi.fn(),
  onDelete = vi.fn(),
}: {
  document?: DocumentSummary;
  onDetails?: (documentId: string) => void;
  onReindex?: (documentId: string) => void;
  onDelete?: (document: DocumentSummary) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button type="button">Outside</button>
      <DocumentActions
        document={document}
        disabled={false}
        open={open}
        onOpenChange={setOpen}
        onDetails={onDetails}
        onReindex={onReindex}
        onDelete={onDelete}
      />
    </div>
  );
}

describe("DocumentActions", () => {
  it("opens the menu from the Actions button", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Actions for notes.md" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Details" })).toBeInTheDocument();
  });

  it("closes when clicking outside", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByRole("button", { name: "Actions for notes.md" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Outside" }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Actions for notes.md" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("closes on Escape and returns focus to the trigger", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Actions for notes.md" });
    await user.click(trigger);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("closes after choosing Details and still runs the action", async () => {
    const user = userEvent.setup();
    const onDetails = vi.fn();
    render(<Harness onDetails={onDetails} />);
    await user.click(screen.getByRole("button", { name: "Actions for notes.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Details" }));
    expect(onDetails).toHaveBeenCalledWith("doc-1");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes after choosing Re-index and still runs the action", async () => {
    const user = userEvent.setup();
    const onReindex = vi.fn();
    render(<Harness onReindex={onReindex} />);
    await user.click(screen.getByRole("button", { name: "Actions for notes.md" }));
    expect(screen.getByRole("menuitem", { name: "Re-index" })).toHaveAttribute(
      "title",
      expect.stringContaining("rebuild"),
    );
    await user.click(screen.getByRole("menuitem", { name: "Re-index" }));
    expect(onReindex).toHaveBeenCalledWith("doc-1");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes after choosing Remove and still runs the action", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<Harness onDelete={onDelete} />);
    await user.click(screen.getByRole("button", { name: "Actions for notes.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Remove" }));
    expect(onDelete).toHaveBeenCalledWith(expect.objectContaining({ document_id: "doc-1" }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
