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
  it("opens History and highlights the active session", async () => {
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
    expect(screen.queryByRole("menu", { name: "Research history" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "History" }));
    expect(screen.getByRole("menu", { name: "Research history" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /Prior work/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.queryByRole("menuitem", { name: "New research" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "History" }));
    expect(screen.queryByRole("menu", { name: "Research history" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "History" }));
    await user.click(screen.getByRole("menuitem", { name: /Later notes/ }));
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
    expect(screen.getByRole("menu", { name: "Research history" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu", { name: "Research history" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "History" }));
    await user.click(document.body);
    expect(screen.queryByRole("menu", { name: "Research history" })).not.toBeInTheDocument();
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
