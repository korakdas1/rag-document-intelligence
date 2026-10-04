import { useRef } from "react";
import { Dialog } from "./ui/Dialog";
import type { DocumentDetail } from "../api/types";
import { formatDocumentWarning } from "../documentWarnings";

type DocumentDetailsProps = {
  detail: DocumentDetail;
  onClose: () => void;
};

function formatWhen(value: string | null | undefined): string {
  if (!value || !String(value).trim()) {
    return "Unavailable";
  }
  return String(value).replace("T", " ").replace("Z", " UTC");
}

function displayValue(value: string | number | null | undefined): string {
  if (value == null || value === "") {
    return "Unavailable";
  }
  return String(value);
}

function warningMessages(detail: DocumentDetail): string[] {
  if (!Array.isArray(detail.warnings)) {
    return [];
  }
  return detail.warnings.filter((item): item is string => typeof item === "string" && item.trim() !== "");
}

function productStatus(detail: DocumentDetail): string {
  if (detail.source_available === false) {
    return "Source missing";
  }
  if (detail.status === "ready") {
    return "Ready";
  }
  if (detail.status === "failed") {
    return "Failed";
  }
  if (detail.status === "chunked" || detail.status === "parsed") {
    return "Indexing…";
  }
  return detail.status ? displayValue(detail.status) : "Unavailable";
}

export function DocumentDetails({ detail, onClose }: DocumentDetailsProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const warnings = warningMessages(detail);
  const warningCount = detail.warning_count ?? warnings.length;

  return (
    <Dialog title={displayValue(detail.filename)} onClose={onClose}
      initialFocusRef={closeRef} dismissOnBackdrop backdropTestId="document-details-backdrop">
      <dl className="detail-list">
        <div>
          <dt>Type</dt>
          <dd>{displayValue(detail.content_type)}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{productStatus(detail)}</dd>
        </div>
        <div>
          <dt>Pages</dt>
          <dd>{detail.page_count ?? "—"}</dd>
        </div>
        <div>
          <dt>Chunks</dt>
          <dd>{detail.chunk_count ?? "—"}</dd>
        </div>
        <div>
          <dt>Ingested</dt>
          <dd>{formatWhen(detail.ingested_at)}</dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>{formatWhen(detail.updated_at)}</dd>
        </div>
        <div>
          <dt>Warnings</dt>
          <dd>{warningCount || "None"}</dd>
        </div>
      </dl>
      {warnings.length ? (
        <div className="detail-warnings">
          <h4>Warnings</h4>
          <ul className="warning-list">
            {warnings.map((warning) => (
              <li key={warning}>{formatDocumentWarning(warning)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <details className="detail-advanced">
        <summary>Developer details</summary>
        <dl className="detail-list">
          <div>
            <dt>Document ID</dt>
            <dd>{displayValue(detail.document_id)}</dd>
          </div>
          <div>
            <dt>Parser</dt>
            <dd>{detail.parser_id || "—"}</dd>
          </div>
          <div>
            <dt>Checksum</dt>
            <dd>{detail.checksum_sha256 || detail.checksum_prefix || "—"}</dd>
          </div>
          <div>
            <dt>Index</dt>
            <dd>{detail.index_status || "—"}</dd>
          </div>
          <div>
            <dt>Chunker</dt>
            <dd>{displayValue(detail.chunker_id)}</dd>
          </div>
        </dl>
        {warnings.length ? (
          <ul className="warning-list">
            {warnings.map((warning) => (
              <li key={`dev-${warning}`}>{warning}</li>
            ))}
          </ul>
        ) : null}
      </details>
      <div className="dialog-actions">
        <button
          ref={closeRef}
          type="button"
          className="btn btn-quiet"
          onClick={onClose}
        >
          Close
        </button>
      </div>
    </Dialog>
  );
}
