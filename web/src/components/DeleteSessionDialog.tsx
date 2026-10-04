import { useRef } from "react";
import { Dialog } from "./ui/Dialog";

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
  const cancelRef = useRef<HTMLButtonElement>(null);

  return (
    <Dialog title="Delete conversation" onClose={onCancel} busy={busy} initialFocusRef={cancelRef}>
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
    </Dialog>
  );
}
