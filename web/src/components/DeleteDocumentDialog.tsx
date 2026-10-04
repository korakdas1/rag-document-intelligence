import { useRef } from "react";
import { Dialog } from "./ui/Dialog";

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
  const cancelRef = useRef<HTMLButtonElement>(null);

  return (
    <Dialog title="Remove document" onClose={onCancel} busy={busy} initialFocusRef={cancelRef}>
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
    </Dialog>
  );
}
