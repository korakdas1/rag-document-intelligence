import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { DocumentSummary } from "../api/types";
import { DocumentSidebar } from "./DocumentSidebar";

const longName =
  "Enough_is_enough_when_the_filename_is_extremely_long_and_must_remain_readable.pdf";

function doc(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    document_id: "doc-1",
    filename: "notes.md",
    content_type: "text/markdown",
    status: "ready",
    page_count: 13,
    chunk_count: 22,
    byte_size: 12,
    warning_count: 0,
    ingested_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    parse_status: "parsed",
    error_message: null,
    ...overrides,
  };
}

const noop = {
  onToggleDocument: vi.fn(),
  onSelectAll: vi.fn(),
  onClearSelection: vi.fn(),
  onUpload: vi.fn(),
};

describe("DocumentSidebar", () => {
  it("lets the file picker select multiple documents", () => {
    render(
      <DocumentSidebar
        documents={[]}
        selectedIds={[]}
        uploading={false}
        {...noop}
      />,
    );
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).toHaveAttribute("multiple");
    expect(screen.getByRole("button", { name: "Add documents" })).toBeInTheDocument();
  });

  it("explains the empty library without onboarding copy", () => {
    render(
      <DocumentSidebar
        documents={[]}
        selectedIds={[]}
        uploading={false}
        {...noop}
      />,
    );
    expect(
      screen.getByText("Add a PDF, Markdown, or text document to start asking questions."),
    ).toBeInTheDocument();
    expect(screen.getByText("Empty")).toBeInTheDocument();
  });

  it("keeps long filenames available and explains all-document search", async () => {
    const user = userEvent.setup();
    const onToggleDocument = vi.fn();
    render(
      <DocumentSidebar
        documents={[
          doc({ filename: longName, content_type: "application/pdf" }),
          doc({ document_id: "doc-2", filename: "second.md" }),
        ]}
        selectedIds={["doc-1", "doc-2"]}
        allDocuments
        uploading={false}
        onToggleDocument={onToggleDocument}
        onSelectAll={vi.fn()}
        onClearSelection={vi.fn()}
        onUpload={vi.fn()}
      />,
    );
    expect(screen.getByTitle(longName)).toBeInTheDocument();
    expect(
      screen.getByText("Include the whole library, including future uploads."),
    ).toBeInTheDocument();
    await user.click(screen.getByText(longName));
    expect(onToggleDocument).toHaveBeenCalledWith("doc-1");
  });

  it("states the subset corpus when documents are selected", () => {
    render(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "second.md" })]}
        selectedIds={["doc-2"]}
        allDocuments={false}
        uploading={false}
        {...noop}
      />,
    );
    expect(screen.getByText("Use a fixed document selection.")).toBeInTheDocument();
  });

  it("shows truthful totals and ready, processing, and attention counts", () => {
    render(
      <DocumentSidebar
        documents={[
          doc(),
          doc({ document_id: "doc-processing", filename: "draft.txt", status: "parsed" }),
          doc({
            document_id: "doc-2",
            filename: "report.pdf",
            source_available: false,
            warning_count: 2,
          }),
        ]}
        selectedIds={[]}
        uploading={false}
        filter=""
        onFilterChange={vi.fn()}
        {...noop}
        onDetails={vi.fn()}
        onReindex={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("3 documents")).toBeInTheDocument();
    expect(screen.getByText("1 ready · 1 processing · 1 needs attention")).toBeInTheDocument();
    expect(screen.getByText("Source missing")).toBeInTheDocument();
    expect(screen.getByText("2 warnings")).toBeInTheDocument();
    expect(screen.getByLabelText("Search documents")).toBeInTheDocument();
  });

  it("shows filter result context without changing selection", () => {
    const onToggleDocument = vi.fn();
    render(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "report.pdf" })]}
        selectedIds={["doc-1"]}
        allDocuments={false}
        uploading={false}
        filter="report"
        onFilterChange={vi.fn()}
        {...noop}
        onToggleDocument={onToggleDocument}
      />,
    );
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
    expect(screen.queryByText("notes.md")).not.toBeInTheDocument();
    expect(screen.getByText("Showing 1 of 2 documents")).toBeInTheDocument();
    expect(onToggleDocument).not.toHaveBeenCalled();
  });

  it("distinguishes no filter matches from an empty library", () => {
    render(<DocumentSidebar documents={[doc()]} selectedIds={[]} allDocuments={false}
      uploading={false} filter="budget" onFilterChange={vi.fn()} {...noop} />);
    expect(screen.getByText("Showing 0 of 1 document")).toBeInTheDocument();
    expect(screen.getByText("No documents match “budget”.")).toBeInTheDocument();
    expect(screen.queryByText("Empty")).not.toBeInTheDocument();
  });

  it("opens only one More menu at a time", async () => {
    const user = userEvent.setup();
    render(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "report.pdf" })]}
        selectedIds={[]}
        uploading={false}
        {...noop}
        onDetails={vi.fn()}
        onReindex={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    const first = screen.getByRole("button", { name: "More actions for notes.md" });
    const second = screen.getByRole("button", { name: "More actions for report.pdf" });
    await user.click(first);
    expect(first).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await user.click(second);
    expect(first).toHaveAttribute("aria-expanded", "false");
    expect(second).toHaveAttribute("aria-expanded", "true");
    expect(screen.getAllByRole("menu")).toHaveLength(1);
  });

  it("checks the master box when every document is selected", () => {
    render(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "second.md" })]}
        selectedIds={["doc-1", "doc-2"]}
        allDocuments
        uploading={false}
        {...noop}
      />,
    );
    const master = screen.getByRole("checkbox", { name: "Ask across all documents" });
    expect(master).toBeChecked();
    expect(master).toHaveAttribute("aria-checked", "true");
  });

  it("clears every document when the checked master is clicked", async () => {
    const user = userEvent.setup();
    const onClearSelection = vi.fn();
    render(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "second.md" })]}
        selectedIds={["doc-1", "doc-2"]}
        allDocuments
        uploading={false}
        onToggleDocument={vi.fn()}
        onSelectAll={vi.fn()}
        onClearSelection={onClearSelection}
        onUpload={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("checkbox", { name: "Ask across all documents" }));
    expect(onClearSelection).toHaveBeenCalledTimes(1);
  });

  it("leaves the master unchecked when nothing is selected", () => {
    render(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "second.md" })]}
        selectedIds={[]}
        allDocuments={false}
        uploading={false}
        {...noop}
      />,
    );
    const master = screen.getByRole("checkbox", { name: "Ask across all documents" });
    expect(master).not.toBeChecked();
    expect(master).toHaveAttribute("aria-checked", "false");
    expect(master).not.toHaveProperty("indeterminate", true);
    expect(
      screen.getByText("No documents selected."),
    ).toBeInTheDocument();
  });

  it("selects every document when the unchecked master is clicked", async () => {
    const user = userEvent.setup();
    const onSelectAll = vi.fn();
    render(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "second.md" })]}
        selectedIds={[]}
        allDocuments={false}
        uploading={false}
        onToggleDocument={vi.fn()}
        onSelectAll={onSelectAll}
        onClearSelection={vi.fn()}
        onUpload={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("checkbox", { name: "Ask across all documents" }));
    expect(onSelectAll).toHaveBeenCalledTimes(1);
  });

  it("exposes an indeterminate master when some documents are selected", () => {
    render(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "second.md" })]}
        selectedIds={["doc-2"]}
        allDocuments={false}
        uploading={false}
        {...noop}
      />,
    );
    const master = screen.getByRole("checkbox", { name: "Ask across all documents" });
    expect(master).not.toBeChecked();
    expect(master).toHaveAttribute("aria-checked", "mixed");
    expect(master).toHaveProperty("indeterminate", true);
  });

  it("selects every document when the indeterminate master is clicked", async () => {
    const user = userEvent.setup();
    const onSelectAll = vi.fn();
    render(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "second.md" })]}
        selectedIds={["doc-2"]}
        allDocuments={false}
        uploading={false}
        onToggleDocument={vi.fn()}
        onSelectAll={onSelectAll}
        onClearSelection={vi.fn()}
        onUpload={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("checkbox", { name: "Ask across all documents" }));
    expect(onSelectAll).toHaveBeenCalledTimes(1);
  });

  it("toggles once from a card click, checkbox click, or keyboard", async () => {
    const user = userEvent.setup();
    const onClearSelection = vi.fn();
    const onSelectAll = vi.fn();
    const { rerender } = render(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "second.md" })]}
        selectedIds={["doc-1", "doc-2"]}
        allDocuments
        uploading={false}
        onToggleDocument={vi.fn()}
        onSelectAll={onSelectAll}
        onClearSelection={onClearSelection}
        onUpload={vi.fn()}
      />,
    );
    await user.click(screen.getByText("All documents"));
    expect(onClearSelection).toHaveBeenCalledTimes(1);
    expect(onSelectAll).not.toHaveBeenCalled();

    rerender(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "second.md" })]}
        selectedIds={[]}
        allDocuments={false}
        uploading={false}
        onToggleDocument={vi.fn()}
        onSelectAll={onSelectAll}
        onClearSelection={onClearSelection}
        onUpload={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("checkbox", { name: "Ask across all documents" }));
    expect(onSelectAll).toHaveBeenCalledTimes(1);
    expect(onClearSelection).toHaveBeenCalledTimes(1);

    const master = screen.getByRole("checkbox", { name: "Ask across all documents" });
    master.focus();
    await user.keyboard(" ");
    expect(onSelectAll).toHaveBeenCalledTimes(2);
    expect(onClearSelection).toHaveBeenCalledTimes(1);
  });

  it("keeps the selected class on the whole card while hovering inner parts", async () => {
    const user = userEvent.setup();
    const onToggleDocument = vi.fn();
    render(
      <DocumentSidebar
        documents={[doc(), doc({ document_id: "doc-2", filename: "second.md" })]}
        selectedIds={["doc-1"]}
        allDocuments={false}
        uploading={false}
        onToggleDocument={onToggleDocument}
        onSelectAll={vi.fn()}
        onClearSelection={vi.fn()}
        onUpload={vi.fn()}
        onDetails={vi.fn()}
        onReindex={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    const selected = screen.getAllByTestId("document-card")[0];
    expect(selected).toHaveClass("is-selected");
    expect(selected).toHaveAttribute("data-selected", "true");
    const unselected = screen.getAllByTestId("document-card")[1];
    expect(unselected).not.toHaveClass("is-selected");
    await user.hover(screen.getByText("notes.md"));
    expect(selected).toHaveClass("is-selected");
    await user.hover(screen.getByRole("button", { name: "More actions for notes.md" }));
    expect(selected).toHaveClass("is-selected");
    expect(unselected).not.toHaveClass("is-selected");
    await user.hover(unselected);
    expect(unselected).not.toHaveClass("is-selected");
    expect(selected).toHaveClass("is-selected");
    await user.click(screen.getByRole("checkbox", { name: /notes.md/ }));
    expect(onToggleDocument).toHaveBeenCalledTimes(1);
  });

  it("keeps upload errors separate from document action errors", () => {
    render(
      <DocumentSidebar
        documents={[doc()]}
        selectedIds={["doc-1"]}
        uploading={false}
        uploadFeedback={{ kind: "result", added: 0, failures: [
          { filename: "photo.png", reason: "Unsupported file type." },
        ] }}
        documentActionError="Could not load document details."
        onToggleDocument={vi.fn()}
        onSelectAll={vi.fn()}
        onClearSelection={vi.fn()}
        onUpload={vi.fn()}
        onDetails={vi.fn()}
        onReindex={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByTestId("upload-error")).toHaveTextContent("Unsupported file type.");
    expect(screen.getByTestId("document-action-error")).toHaveTextContent(
      "Could not load document details.",
    );
    expect(screen.getByTestId("upload-error")).not.toHaveTextContent(
      "Could not load document details.",
    );
  });

  it("shows Re-indexing while a document is busy", () => {
    render(
      <DocumentSidebar
        documents={[doc()]}
        selectedIds={["doc-1"]}
        uploading={false}
        busyDocumentId="doc-1"
        busyKind="reindex"
        onToggleDocument={vi.fn()}
        onSelectAll={vi.fn()}
        onClearSelection={vi.fn()}
        onUpload={vi.fn()}
        onDetails={vi.fn()}
        onReindex={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("Re-indexing…")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /notes.md/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "More actions for notes.md" })).toBeDisabled();
  });

  it("keeps a full fixed subset mixed instead of claiming canonical ALL", () => {
    render(<DocumentSidebar documents={[doc(), doc({ document_id: "doc-2" })]}
      selectedIds={["doc-1", "doc-2"]} allDocuments={false} uploading={false} {...noop} />);
    const master = screen.getByRole("checkbox", { name: "Ask across all documents" });
    expect(master).not.toBeChecked();
    expect(master).toHaveAttribute("aria-checked", "mixed");
    expect(screen.getByText("Use a fixed document selection.")).toBeInTheDocument();
  });

  it("keeps canonical ALL under an active filename filter", async () => {
    const onClearSelection = vi.fn();
    render(<DocumentSidebar documents={[doc(), doc({ document_id: "doc-2", filename: "report.pdf" })]}
      selectedIds={["doc-1", "doc-2"]} allDocuments uploading={false} filter="report"
      onFilterChange={vi.fn()} {...noop} onClearSelection={onClearSelection} />);
    const master = screen.getByRole("checkbox", { name: "Ask across all documents" });
    expect(master).toBeChecked();
    await userEvent.setup().click(master);
    expect(onClearSelection).toHaveBeenCalledOnce();
  });

  it("shows stable IDs only for duplicate filenames and toggles the correct identity", async () => {
    const onToggleDocument = vi.fn();
    render(<DocumentSidebar documents={[
      doc({ document_id: "abcdef123456" }),
      doc({ document_id: "98765432ffff" }),
      doc({ document_id: "unique-id", filename: "unique.pdf" }),
    ]} selectedIds={[]} allDocuments={false} uploading={false} {...noop} onToggleDocument={onToggleDocument} />);
    expect(screen.getByText("ID abcdef12")).toBeInTheDocument();
    expect(screen.getByText("ID 98765432")).toBeInTheDocument();
    expect(screen.queryByText("ID unique-i")).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("checkbox", { name: /ID 98765432/ }));
    expect(onToggleDocument).toHaveBeenCalledWith("98765432ffff");
  });
});
