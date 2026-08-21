import { useEffect, useId, useRef, useState } from "react";
import type { SessionSummary } from "../api/types";

type SessionSwitcherProps = {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  currentTitle?: string;
  disabled?: boolean;
  onOpen: (sessionId: string) => void;
  onRename: (session: SessionSummary) => void;
  onDelete: (session: SessionSummary) => void;
};

function formatUpdated(value: string): string {
  return value.replace("T", " ").replace("Z", "").replace("+00:00", " UTC");
}

export function SessionSwitcher({
  sessions,
  activeSessionId,
  currentTitle,
  disabled = false,
  onOpen,
  onRename,
  onDelete,
}: SessionSwitcherProps) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const filterId = useId();
  const query = filter.trim().toLowerCase();
  const visible = query
    ? sessions.filter((item) => item.title.toLowerCase().includes(query))
    : sessions;

  useEffect(() => {
    if (!open) {
      return;
    }
    function onPointerDown(event: PointerEvent) {
      if (rootRef.current?.contains(event.target as Node)) {
        return;
      }
      setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    }
    globalThis.document.addEventListener("pointerdown", onPointerDown);
    globalThis.document.addEventListener("keydown", onKeyDown);
    return () => {
      globalThis.document.removeEventListener("pointerdown", onPointerDown);
      globalThis.document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="session-switcher">
      <button
        ref={triggerRef}
        type="button"
        className="btn btn-quiet"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label="History"
        title={currentTitle}
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
      >
        History
      </button>
      {open ? (
        <div id={menuId} className="session-menu" role="menu" aria-label="Research history">
          <div className="session-menu-head">
            <label htmlFor={filterId} className="visually-hidden">
              Search sessions
            </label>
            <input
              id={filterId}
              type="search"
              value={filter}
              placeholder="Search sessions…"
              onChange={(event) => setFilter(event.target.value)}
            />
          </div>
          {visible.length === 0 ? (
            <p className="muted session-empty">No saved conversations yet.</p>
          ) : (
            <ul className="session-list">
              {visible.map((session) => {
                const active = session.session_id === activeSessionId;
                return (
                  <li key={session.session_id}>
                    <div className={`session-item${active ? " is-active" : ""}`}>
                      <button
                        type="button"
                        role="menuitem"
                        aria-current={active ? "true" : undefined}
                        onClick={() => {
                          setOpen(false);
                          onOpen(session.session_id);
                        }}
                      >
                        <span className="session-title">{session.title}</span>
                        <span className="session-meta">
                          {session.turn_count} turn{session.turn_count === 1 ? "" : "s"} ·{" "}
                          {formatUpdated(session.updated_at)}
                        </span>
                      </button>
                      <div className="session-item-actions">
                        <button
                          type="button"
                          className="btn-menu"
                          aria-label={`Rename ${session.title}`}
                          onClick={() => {
                            setOpen(false);
                            onRename(session);
                          }}
                        >
                          Rename
                        </button>
                        <button
                          type="button"
                          className="btn-menu"
                          aria-label={`Delete ${session.title}`}
                          onClick={() => {
                            setOpen(false);
                            onDelete(session);
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
