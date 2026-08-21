import { useEffect, useId, useRef } from "react";

type DeleteDocumentDialogProps = {
  filename: string;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
};

export function DeleteDocumentDialog({
  filename,
  busy,
  error,
  onCancel,
  onConfirm,
}: DeleteDocumentDialogProps) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
  }, []);

  return (
    <div className="dialog-backdrop">
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={(event) => {
          if (event.key === "Escape" && !busy) {
            onCancel();
          }
        }}
      >
        <h3 id={titleId}>Remove document</h3>
        <p>
          Remove <strong>{filename}</strong> from the library?
        </p>
        <p className="hint">
          Indexed chunks and vectors will be removed. The original source file is not deleted.
        </p>
        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}
        <div className="dialog-actions">
          <button
            ref={cancelRef}
            type="button"
            className="btn btn-quiet"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-danger"
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? "Removing…" : "Remove"}
          </button>
        </div>
      </div>
    </div>
  );
}
