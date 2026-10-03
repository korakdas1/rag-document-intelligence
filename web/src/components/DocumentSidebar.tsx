import { useEffect, useId, useRef, useState } from "react";
import type { DocumentStatus, DocumentSummary } from "../api/types";
import { DocumentActions } from "./DocumentActions";
import { sanitizeUploadError } from "../userErrors";

type DocumentSidebarProps = {
  documents: DocumentSummary[];
  selectedIds: string[];
  allDocuments?: boolean;
  uploading: boolean;
  uploadError: string | null;
  uploadStatus?: string | null;
  libraryLoadError?: string | null;
  documentActionError?: string | null;
  busyDocumentId?: string | null;
  busyKind?: "reindex" | "delete" | null;
  filter?: string;
  onFilterChange?: (value: string) => void;
  onToggleDocument: (documentId: string) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onUpload: (files: File[]) => void;
  onDismissUploadError?: () => void;
  onRetryLoad?: () => void;
  onDetails?: (documentId: string) => void;
  onReindex?: (documentId: string) => void;
  onDelete?: (document: DocumentSummary) => void;
};

function typeLabel(contentType: string): string {
  if (contentType.includes("pdf")) {
    return "PDF";
  }
  if (contentType.includes("markdown")) {
    return "Markdown";
  }
  return "Text";
}

function statusLabel(doc: DocumentSummary): string {
  if (doc.source_available === false) {
    return "Source missing";
  }
  switch (doc.status) {
    case "ready":
      return "Ready";
    case "failed":
      return "Failed";
    case "chunked":
    case "parsed":
      return "Indexing…";
    default:
      return doc.status;
  }
}

function statusClass(status: DocumentStatus, sourceAvailable?: boolean): string {
  if (sourceAvailable === false) {
    return "failed";
  }
  if (status === "ready") {
    return "ready";
  }
  if (status === "failed") {
    return "failed";
  }
  return "";
}

export function DocumentSidebar({
  documents,
  selectedIds,
  allDocuments,
  uploading,
  uploadError,
  uploadStatus = null,
  libraryLoadError = null,
  documentActionError = null,
  busyDocumentId = null,
  busyKind = null,
  filter = "",
  onFilterChange,
  onToggleDocument,
  onSelectAll,
  onClearSelection,
  onUpload,
  onDismissUploadError,
  onRetryLoad,
  onDetails,
  onReindex,
  onDelete,
}: DocumentSidebarProps) {
  const inputId = useId();
  const filterId = useId();
  const fileRef = useRef<HTMLInputElement>(null);
  const masterRef = useRef<HTMLInputElement>(null);
  const selectedSet = new Set(selectedIds);
  const selectedCount = documents.filter((doc) => selectedSet.has(doc.document_id)).length;
  const allSelected = allDocuments ?? (documents.length > 0 && selectedCount === documents.length);
  const noneSelected = selectedCount === 0;
  const indeterminate = selectedCount > 0 && !allSelected;
  const query = filter.trim().toLowerCase();
  const visible = query
    ? documents.filter((doc) => doc.filename.toLowerCase().includes(query))
    : documents;
  const showActions = Boolean(onDetails && onReindex && onDelete);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  useEffect(() => {
    if (masterRef.current) {
      masterRef.current.indeterminate = indeterminate;
    }
  }, [indeterminate]);

  return (
    <aside className="sidebar" aria-label="Document library">
      <header className="pane-heading">
        <h2>Documents</h2>
        <span className="muted">
          {documents.length === 0 ? "Empty" : `${documents.length} indexed`}
        </span>
      </header>
      <div className="pane-scroll">
        <div className="sidebar-actions">
          <input
            id={inputId}
            ref={fileRef}
            type="file"
            multiple
            accept=".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown"
            className="visually-hidden"
            disabled={uploading || Boolean(busyDocumentId)}
            onChange={(event) => {
              const files = event.target.files ? Array.from(event.target.files) : [];
              if (files.length > 0) {
                onUpload(files);
              }
              event.target.value = "";
            }}
          />
          <button
            type="button"
            className="btn btn-primary btn-block"
            disabled={uploading || Boolean(busyDocumentId)}
            onClick={() => fileRef.current?.click()}
          >
            {uploading ? "Uploading…" : "Add documents"}
          </button>
          <p className="hint">PDF, Markdown, or text. Choose one or more files. Indexing runs before the upload finishes.</p>
          {uploadStatus ? (
            <p className="hint" role="status" aria-live="polite" data-testid="upload-status">
              {uploadStatus}
            </p>
          ) : null}
          {uploadError ? (
            <p className="error upload-error" role="alert" aria-live="polite" data-testid="upload-error">
              <span>{uploadError}</span>
              {onDismissUploadError ? (
                <button
                  type="button"
                  className="error-dismiss"
                  onClick={onDismissUploadError}
                  aria-label="Dismiss upload message"
                >
                  ×
                </button>
              ) : null}
            </p>
          ) : null}
        </div>
        {documents.length === 0 ? (
          <p className="empty">
            {libraryLoadError
              ? "The document library could not be loaded."
              : "Add a PDF, Markdown, or text document to start asking questions."}
            {libraryLoadError && onRetryLoad ? (
              <>
                {" "}
                <button type="button" className="btn btn-quiet" onClick={onRetryLoad}>
                  Retry
                </button>
              </>
            ) : null}
          </p>
        ) : (
          <>
            {onFilterChange ? (
              <div className="library-filter">
                <label htmlFor={filterId} className="visually-hidden">
                  Search documents
                </label>
                <input
                  id={filterId}
                  type="search"
                  value={filter}
                  placeholder="Search documents…"
                  onChange={(event) => onFilterChange(event.target.value)}
                />
              </div>
            ) : null}
            {documentActionError ? (
              <p className="error" role="alert" data-testid="document-action-error">
                {documentActionError}
              </p>
            ) : null}
            <label className={`doc-row select-all${allSelected ? " is-selected" : ""}`}>
              <input
                ref={masterRef}
                type="checkbox"
                checked={allSelected}
                aria-checked={indeterminate ? "mixed" : allSelected}
                aria-label="Ask across all documents"
                onChange={() => {
                  if (allSelected) {
                    onClearSelection();
                  } else {
                    onSelectAll();
                  }
                }}
              />
              <span>
                <span className="doc-name">Ask across all documents</span>
                <span className="doc-sub">
                  {allSelected
                    ? "The next question searches every indexed document. Uncheck a document to search a subset."
                    : noneSelected
                      ? "Select at least one document to ask a question."
                      : `The next question searches ${selectedCount} selected document${selectedCount === 1 ? "" : "s"}.`}
                </span>
              </span>
            </label>
            <ul className="doc-list">
              {visible.map((doc) => {
                const checked = selectedSet.has(doc.document_id);
                const sameName =
                  documents.filter((item) => item.filename === doc.filename).length > 1;
                const busy = busyDocumentId === doc.document_id;
                return (
                  <li key={doc.document_id}>
                    <div
                      className={`doc-item${checked ? " is-selected" : ""}`}
                      data-testid="document-card"
                      data-selected={checked ? "true" : "false"}
                    >
                      <label className="doc-row">
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={busy}
                          onChange={() => onToggleDocument(doc.document_id)}
                        />
                        <span className="doc-meta">
                          <span className="doc-name" title={doc.filename}>
                            {doc.filename}
                          </span>
                          {sameName ? (
                            <span className="muted">{doc.document_id.slice(0, 8)}</span>
                          ) : null}
                          <span className="doc-sub">
                            <span>{typeLabel(doc.content_type)}</span>
                            <span
                              className={`status-dot ${statusClass(doc.status, doc.source_available)}`}
                            >
                              {busy
                                ? busyKind === "reindex"
                                  ? "Re-indexing…"
                                  : "Processing…"
                                : statusLabel(doc)}
                            </span>
                            {doc.page_count ? <span>{doc.page_count} pp.</span> : null}
                            <span>{doc.chunk_count} chunks</span>
                            {doc.warning_count ? (
                              <span className="warn-count">{doc.warning_count} warnings</span>
                            ) : null}
                          </span>
                          {doc.error_message ? (
                            <span className="error">
                              {sanitizeUploadError(doc.error_message, doc.filename)}
                            </span>
                          ) : null}
                        </span>
                      </label>
                      {showActions ? (
                        <DocumentActions
                          document={doc}
                          disabled={busy || uploading}
                          open={openMenuId === doc.document_id}
                          onOpenChange={(next) =>
                            setOpenMenuId(next ? doc.document_id : null)
                          }
                          onDetails={onDetails!}
                          onReindex={onReindex!}
                          onDelete={onDelete!}
                        />
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
            {query && visible.length === 0 ? (
              <p className="empty">No documents match that name.</p>
            ) : null}
          </>
        )}
      </div>
    </aside>
  );
}
