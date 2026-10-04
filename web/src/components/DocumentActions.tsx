import { useEffect, useId, useRef } from "react";
import type { DocumentSummary } from "../api/types";

type DocumentActionsProps = {
  document: DocumentSummary;
  disabled: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDetails: (documentId: string) => void;
  onReindex: (documentId: string) => void;
  onDelete: (document: DocumentSummary) => void;
};

export function DocumentActions({
  document,
  disabled,
  open,
  onOpenChange,
  onDetails,
  onReindex,
  onDelete,
}: DocumentActionsProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const onOpenChangeRef = useRef(onOpenChange);
  const menuId = useId();

  useEffect(() => {
    onOpenChangeRef.current = onOpenChange;
  }, [onOpenChange]);

  useEffect(() => {
    if (!open) {
      return;
    }

    function onPointerDown(event: PointerEvent) {
      if (rootRef.current?.contains(event.target as Node)) {
        return;
      }
      onOpenChangeRef.current(false);
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }
      event.preventDefault();
      onOpenChangeRef.current(false);
      triggerRef.current?.focus();
    }

    globalThis.document.addEventListener("pointerdown", onPointerDown);
    globalThis.document.addEventListener("keydown", onKeyDown);
    return () => {
      globalThis.document.removeEventListener("pointerdown", onPointerDown);
      globalThis.document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (disabled && open) {
      onOpenChangeRef.current(false);
    }
  }, [disabled, open]);

  function choose(action: () => void, opensDialog = false) {
    // The menu item unmounts; retain the exact persistent opener for dialogs.
    if (opensDialog) triggerRef.current?.focus();
    onOpenChange(false);
    action();
  }

  return (
    <div
      ref={rootRef}
      className="doc-menu"
      onClick={(event) => event.stopPropagation()}
    >
      <button
        ref={triggerRef}
        type="button"
        className="btn-menu"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={`Actions for ${document.filename}`}
        disabled={disabled}
        onClick={() => onOpenChange(!open)}
      >
        Actions
      </button>
      {open ? (
        <ul id={menuId} className="doc-menu-list" role="menu">
          <li role="none">
            <button
              type="button"
              role="menuitem"
              onClick={() => choose(() => onDetails(document.document_id), true)}
            >
              Details
            </button>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
              disabled={document.source_available === false}
              onClick={() => choose(() => onReindex(document.document_id))}
              title="Reprocess this document and rebuild its searchable chunks and index. Existing answers stay the same; new questions use the rebuilt index."
            >
              Re-index
            </button>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
              onClick={() => choose(() => onDelete(document), true)}
            >
              Remove
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  );
}
