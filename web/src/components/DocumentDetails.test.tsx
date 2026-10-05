import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DeleteDocumentDialog } from "./DeleteDocumentDialog";
import { DocumentDetails } from "./DocumentDetails";

describe("library dialogs", () => {
  it("requires confirmation copy before remove", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <DeleteDocumentDialog
        filename="notes.md"
        busy={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />,
    );
    expect(screen.getByRole("dialog", { name: "Remove document" })).toBeInTheDocument();
    expect(screen.getByText("notes.md")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(onConfirm).toHaveBeenCalled();
  });

  it("shows user metadata and keeps internals behind developer details", () => {
    render(
      <DocumentDetails
        detail={{
          document_id: "doc-1",
          filename: "notes.md",
          content_type: "text/markdown",
          status: "ready",
          page_count: 3,
          chunk_count: 8,
          byte_size: 12,
          warning_count: 1,
          ingested_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-02T00:00:00Z",
          parse_status: "parsed",
          error_message: null,
          source_available: true,
          checksum_prefix: "abc123",
          chunker_id: "structure.v1:test",
          parser_id: "markdown.v1",
          warnings: ["empty heading"],
          checksum_sha256: "abc123def456",
          index_status: "ready",
        }}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole("dialog", { name: "notes.md" })).toBeInTheDocument();
    expect(screen.getByText("markdown.v1")).toBeInTheDocument();
    expect(screen.getAllByText("empty heading").length).toBeGreaterThan(0);
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("abc123def456")).toBeInTheDocument();
    expect(screen.getByText("structure.v1:test")).toBeInTheDocument();
    expect(screen.getByText("Index").nextElementSibling).toHaveTextContent("ready");
  });

  it.each([1, 2])("keeps %s chunk available as a labeled Details count", (count) => {
    render(<DocumentDetails detail={{
      document_id: "doc-1", filename: "counts.md", content_type: "text/markdown",
      status: "ready", page_count: count, chunk_count: count, byte_size: 12,
      warning_count: 0, ingested_at: "", updated_at: "", parse_status: "parsed",
      error_message: null, chunker_id: "test", parser_id: "markdown.v1", warnings: [],
    }} onClose={vi.fn()} />);
    expect(screen.getByText("Chunks").nextElementSibling).toHaveTextContent(String(count));
    expect(screen.getByText("Pages").nextElementSibling).toHaveTextContent(String(count));
    expect(screen.queryByText("1 chunks")).not.toBeInTheDocument();
    expect(screen.queryByText("1 pages")).not.toBeInTheDocument();
  });

  it("shows persisted warning details in the main Details view", () => {
    render(
      <DocumentDetails
        detail={{
          document_id: "doc-1",
          filename: "grade.pdf",
          content_type: "application/pdf",
          status: "ready",
          page_count: 3,
          chunk_count: 4,
          byte_size: 12,
          warning_count: 3,
          ingested_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          parse_status: "parsed",
          error_message: null,
          chunker_id: "structure.v1:test",
          parser_id: "pdf.pypdf.v1",
          warnings: [
            "page_1_has_xobjects_not_extracted_as_text",
            "page_2_has_xobjects_not_extracted_as_text",
            "page_3_has_xobjects_not_extracted_as_text",
          ],
        }}
        onClose={vi.fn()}
      />,
    );
    expect(
      screen.getByText("Page 1 has images or graphics that were not extracted as text."),
    ).toBeInTheDocument();
    expect(screen.getByText("page_1_has_xobjects_not_extracted_as_text")).toBeInTheDocument();
  });

  it("renders unavailable values instead of crashing on optional metadata", () => {
    render(
      <DocumentDetails
        detail={{
          document_id: "doc-1",
          filename: "notes.md",
          content_type: "text/markdown",
          status: "ready",
          page_count: null,
          chunk_count: 0,
          byte_size: 0,
          warning_count: 0,
          ingested_at: "",
          updated_at: "",
          parse_status: "parsed",
          error_message: null,
          chunker_id: "structure.v1:test",
          parser_id: null,
          warnings: undefined as unknown as string[],
        }}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole("dialog", { name: "notes.md" })).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText("None")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
  });

  it("closes the details dialog", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <DocumentDetails
        detail={{
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
          chunker_id: "structure.v1:test",
          parser_id: "markdown.v1",
          warnings: [],
        }}
        onClose={onClose}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("closes Details on backdrop click and Escape, but not on inside click", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <DocumentDetails
        detail={{
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
          chunker_id: "structure.v1:test",
          parser_id: "markdown.v1",
          warnings: [],
        }}
        onClose={onClose}
      />,
    );
    fireEvent.mouseDown(screen.getByRole("dialog", { name: "notes.md" }));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.mouseDown(screen.getByTestId("document-details-backdrop"));
    expect(onClose).toHaveBeenCalledTimes(1);
    onClose.mockClear();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not close Remove confirmation from the backdrop", async () => {
    const onCancel = vi.fn();
    render(
      <DeleteDocumentDialog
        filename="notes.md"
        busy={false}
        error={null}
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />,
    );
    const dialog = screen.getByRole("dialog", { name: "Remove document" });
    fireEvent.mouseDown(dialog.parentElement as HTMLElement);
    expect(onCancel).not.toHaveBeenCalled();
  });
});

describe("destructive document focus", () => {
  it("starts on Cancel and contains focus while busy without dismissing", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    const { rerender } = render(<DeleteDocumentDialog filename="notes.md" busy={false}
      error={null} onCancel={onCancel} onConfirm={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Remove" })).toHaveFocus();
    rerender(<DeleteDocumentDialog filename="notes.md" busy error={null} onCancel={onCancel} onConfirm={vi.fn()} />);
    await user.tab(); await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog")).toHaveFocus();
    expect(onCancel).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Removing…" })).toBeDisabled();
  });
});
