import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { SessionSummary } from "../api/types";
import { DeleteSessionDialog } from "./DeleteSessionDialog";
import { RenameSessionDialog } from "./RenameSessionDialog";
import { SessionSwitcher } from "./SessionSwitcher";

function session(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    session_id: "sess-1",
    title: "Prior work",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    turn_count: 3,
    all_documents: true,
    ...overrides,
  };
}

describe("SessionSwitcher", () => {
  it("opens a nonmodal History dialog, focuses search, and marks the active session", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    render(
      <SessionSwitcher
        sessions={[session(), session({ session_id: "sess-2", title: "Later notes" })]}
        activeSessionId="sess-1"
        currentTitle="Prior work"
        onOpen={onOpen}
        onRename={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    const trigger = screen.getByRole("button", { name: "History" });
    expect(trigger).toHaveAttribute("aria-haspopup", "dialog");
    expect(screen.queryByRole("dialog", { name: "Research history" })).not.toBeInTheDocument();
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "Research history" })).not.toHaveAttribute("aria-modal");
    expect(screen.getByRole("searchbox", { name: "Search sessions" })).toHaveFocus();
    expect(screen.getByText("Prior work", { selector: ".session-title" }).closest("button")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.queryByRole("button", { name: "New research" })).not.toBeInTheDocument();
    await user.click(trigger);
    expect(screen.queryByRole("dialog", { name: "Research history" })).not.toBeInTheDocument();
    await user.click(trigger);
    await user.click(screen.getByText("Later notes", { selector: ".session-title" }).closest("button")!);
    expect(onOpen).toHaveBeenCalledWith("sess-2");
  });

  it("closes History on Escape and outside click", async () => {
    const user = userEvent.setup();
    render(
      <SessionSwitcher
        sessions={[session()]}
        activeSessionId="sess-1"
        onOpen={vi.fn()}
        onRename={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "History" }));
    expect(screen.getByRole("dialog", { name: "Research history" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Research history" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "History" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "History" }));
    await user.click(document.body);
    expect(screen.queryByRole("dialog", { name: "Research history" })).not.toBeInTheDocument();
  });

  it("distinguishes an empty history from a filtered no-match state", async () => {
    const user = userEvent.setup();
    const props = { activeSessionId: null, onOpen: vi.fn(), onRename: vi.fn(), onDelete: vi.fn() };
    const { rerender } = render(<SessionSwitcher sessions={[]} {...props} />);
    await user.click(screen.getByRole("button", { name: "History" }));
    expect(screen.getByText("No saved conversations yet.")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    rerender(<SessionSwitcher sessions={[session()]} {...props} />);
    await user.click(screen.getByRole("button", { name: "History" }));
    await user.type(screen.getByRole("searchbox", { name: "Search sessions" }), "harbor");
    expect(screen.getByText("No conversations match ‘harbor’." )).toBeInTheDocument();
    expect(screen.queryByText("No saved conversations yet.")).not.toBeInTheDocument();
  });
});

describe("session dialogs", () => {
  it("rejects an empty rename", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <RenameSessionDialog title="Prior work" busy={false} error={null} onCancel={vi.fn()} onConfirm={onConfirm} />,
    );
    await user.clear(screen.getByLabelText("Session title"));
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("explains that deleting a session keeps documents", () => {
    render(
      <DeleteSessionDialog
        title="Prior work"
        busy={false}
        error={null}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByText(/Indexed documents are not deleted/)).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Delete conversation" })).toBeInTheDocument();
  });
});


describe("session dialog focus integration", () => {
  it.each(["Rename", "Delete"])("returns %s to History after its menu item unmounts", async (action) => {
    function Harness() {
      const [dialog, setDialog] = useState<string | null>(null);
      return <>
        <SessionSwitcher sessions={[session()]} activeSessionId="sess-1" onOpen={vi.fn()}
          onRename={() => setDialog("Rename")} onDelete={() => setDialog("Delete")} />
        {dialog === "Rename" && <RenameSessionDialog title="Prior work" busy={false} error={null}
          onCancel={() => setDialog(null)} onConfirm={vi.fn()} />}
        {dialog === "Delete" && <DeleteSessionDialog title="Prior work" busy={false} error={null}
          onCancel={() => setDialog(null)} onConfirm={vi.fn()} />}
      </>;
    }
    const user = userEvent.setup(); render(<Harness />);
    await user.click(screen.getByRole("button", { name: "History" }));
    await user.click(screen.getByRole("button", { name: `${action} Prior work` }));
    if (action === "Rename") {
      const input = screen.getByLabelText("Session title") as HTMLInputElement;
      expect(input).toHaveFocus();
      expect(input.selectionStart).toBe(0); expect(input.selectionEnd).toBe(10);
    } else {
      expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    }
    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "History" })).toHaveFocus();
  });

  it.each(["Rename", "Delete"])("does not dismiss a busy %s dialog", async (kind) => {
    const onCancel = vi.fn(); const user = userEvent.setup();
    const props = { title: "Prior work", busy: true, error: null, onCancel, onConfirm: vi.fn() };
    render(kind === "Rename" ? <RenameSessionDialog {...props} /> : <DeleteSessionDialog {...props} />);
    expect(screen.getByRole("dialog")).toHaveFocus();
    await user.keyboard("{Escape}"); await user.tab();
    expect(onCancel).not.toHaveBeenCalled(); expect(screen.getByRole("dialog")).toHaveFocus();
  });
});
