import { useEffect, useId, useRef } from "react";

type DeleteSessionDialogProps = {
  title: string;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
};

export function DeleteSessionDialog({
  title,
  busy,
  error,
  onCancel,
  onConfirm,
}: DeleteSessionDialogProps) {
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
        <h3 id={titleId}>Delete conversation</h3>
        <p>
          Delete <strong>{title}</strong>? This removes the saved conversation only.
        </p>
        <p className="hint">Indexed documents are not deleted.</p>
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
            {busy ? "Deleting…" : "Delete conversation"}
          </button>
        </div>
      </div>
    </div>
  );
}
