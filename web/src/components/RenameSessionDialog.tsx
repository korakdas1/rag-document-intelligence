import { useId, useRef, useState } from "react";
import { Dialog } from "./ui/Dialog";

type RenameSessionDialogProps = {
  title: string;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: (title: string) => void;
};

export function RenameSessionDialog({
  title,
  busy,
  error,
  onCancel,
  onConfirm,
}: RenameSessionDialogProps) {
  const titleId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState(title);

  const trimmed = value.trim();

  return (
    <Dialog title="Rename conversation" onClose={onCancel} busy={busy} initialFocusRef={inputRef} selectInitialText>
      <label className="visually-hidden" htmlFor={`${titleId}-input`}>
        Session title
      </label>
      <input
        ref={inputRef}
        id={`${titleId}-input`}
        value={value}
        maxLength={80}
        disabled={busy}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && trimmed && !busy) {
            onConfirm(trimmed);
          }
        }}
      />
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="dialog-actions">
        <button type="button" className="btn btn-quiet" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy || !trimmed}
          onClick={() => onConfirm(trimmed)}
        >
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </Dialog>
  );
}
