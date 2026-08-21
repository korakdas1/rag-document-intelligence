import { useEffect, useId, useRef, useState } from "react";

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

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const trimmed = value.trim();

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
        <h3 id={titleId}>Rename conversation</h3>
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
      </div>
    </div>
  );
}
