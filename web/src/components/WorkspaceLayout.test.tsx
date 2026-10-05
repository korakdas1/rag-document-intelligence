import { StrictMode, useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkspaceLayout, type WorkspacePane } from "./WorkspaceLayout";
import { DocumentSidebar } from "./DocumentSidebar";
import { DocumentDetails } from "./DocumentDetails";
import { DeleteDocumentDialog } from "./DeleteDocumentDialog";
import type { DocumentDetail } from "../api/types";

const doc: DocumentDetail = {
  document_id: "demo-1", filename: "Synthetic study.md", content_type: "text/markdown",
  status: "ready", page_count: 1, chunk_count: 2, byte_size: 10, warning_count: 0,
  ingested_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
  parse_status: "parsed", error_message: null, warnings: [], chunker_id: "demo.v1", parser_id: "text",
};

function media(mode: "wide" | "split" | "mobile") {
  let current = mode;
  const listeners = new Set<() => void>();
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("1280") ? current === "wide" : current !== "mobile",
    addEventListener: (_: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
  }));
  return (next: typeof mode) => act(() => { current = next; listeners.forEach((listener) => listener()); });
}
function Harness() {
  const [pane, setPane] = useState<WorkspacePane>("workspace");
  const [selected, setSelected] = useState(true);
  const [filter, setFilter] = useState("");
  const [removed, setRemoved] = useState(false);
  const [dialog, setDialog] = useState<"details" | "remove" | null>(null);
  return <>
    <WorkspaceLayout pane={pane} onPaneChange={setPane} documents={
      <DocumentSidebar documents={removed ? [] : [doc]} selectedIds={selected ? [doc.document_id] : []}
        uploading={false} filter={filter} onFilterChange={setFilter}
        onToggleDocument={() => setSelected(!selected)} onSelectAll={() => setSelected(true)}
        onClearSelection={() => setSelected(false)} onUpload={vi.fn()}
        onDetails={() => setDialog("details")} onDelete={() => setDialog("remove")} onReindex={vi.fn()} />
    } evidence={<section aria-label="Sources"><div className="pane-scroll" data-testid="source-scroll"><button>Source S1</button></div></section>}>
      <main aria-label="Research conversation"><div className="pane-scroll" data-testid="turn-scroll">Saved answer</div>
        <textarea aria-label="Question draft" defaultValue="Preserve this draft" /></main>
    </WorkspaceLayout>
    {dialog === "details" && <DocumentDetails detail={doc} onClose={() => setDialog(null)} />}
    {dialog === "remove" && <DeleteDocumentDialog filename={doc.filename} busy={false} error={null}
      onCancel={() => setDialog(null)} onConfirm={() => { setRemoved(true); setDialog(null); }} />}
  </>;
}
afterEach(() => vi.unstubAllGlobals());

describe("Workspace shell", () => {
  it("exposes all three desktop regions without duplicate Documents navigation", () => {
    media("wide"); render(<Harness />);
    expect(screen.getByRole("complementary", { name: "Document library" })).toBeVisible();
    expect(screen.getByRole("main")).toBeVisible();
    expect(screen.getByRole("region", { name: "Sources" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Documents" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Add documents" })).toHaveLength(1);
  });

  it.each(["close", "escape", "backdrop"])("opens one tablet library and restores its trigger after %s", async (method) => {
    media("split"); const user = userEvent.setup(); render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Documents" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(screen.getByRole("main")).toBeVisible();
    expect(screen.getByRole("region", { name: "Sources" })).toBeVisible();
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "Documents" })).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("button", { name: "Close Documents" })).toHaveFocus();
    expect(screen.getAllByRole("button", { name: "Add documents" })).toHaveLength(1);
    expect(screen.queryByRole("main")).not.toBeInTheDocument();
    if (method === "close") await user.click(screen.getByRole("button", { name: "Close Documents" }));
    if (method === "escape") await user.keyboard("{Escape}");
    if (method === "backdrop") await user.click(screen.getByTestId("documents-backdrop"));
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("main")).toBeVisible();
    expect(document.body.style.overflow).not.toBe("hidden");
  });

  it("contains keyboard and attempted outside focus in the drawer", async () => {
    media("split"); const user = userEvent.setup(); render(<Harness />);
    const outside = screen.getByRole("button", { name: "Documents" });
    await user.click(outside);
    const close = screen.getByRole("button", { name: "Close Documents" });
    await user.tab({ shift: true });
    expect(screen.getByRole("button", { name: /More actions for/ })).toHaveFocus();
    await user.tab(); expect(close).toHaveFocus();
    outside.focus(); expect(close).toHaveFocus();
    for (let i = 0; i < 12; i++) {
      await user.tab(); expect(screen.getByRole("dialog")).toContainElement(document.activeElement as HTMLElement);
    }
  });

  it.each(["Details", "Remove"])("makes %s the active layer and returns through both modal levels", async (action) => {
    media("split"); const user = userEvent.setup(); render(<StrictMode><Harness /></StrictMode>);
    const trigger = screen.getByRole("button", { name: "Documents" });
    await user.click(trigger);
    const actions = screen.getByRole("button", { name: /More actions for/ });
    await user.click(actions); await user.click(screen.getByRole("menuitem", { name: action }));
    const top = screen.getByRole("dialog");
    expect(top).not.toHaveAccessibleName("Documents");
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    await user.tab(); await user.tab({ shift: true }); expect(top).toContainElement(document.activeElement as HTMLElement);
    // Even synthetic delivery to the inert lower backdrop must not close it.
    fireEvent.mouseDown(screen.getByTestId("documents-backdrop"));
    await user.keyboard("{Escape}");
    await waitFor(() => expect(actions).toHaveFocus());
    expect(screen.getByRole("dialog", { name: "Documents" })).toBeVisible();
    expect(document.body.style.overflow).toBe("hidden");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(screen.getByRole("main")).toBeVisible();
    expect(document.body.querySelector("[inert]")).toBeNull();
  });

  it("returns to the surviving library landmark after a nested removal deletes its opener", async () => {
    media("split"); const user = userEvent.setup(); render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Documents" });
    await user.click(trigger);
    await user.click(screen.getByRole("button", { name: /More actions for/ }));
    await user.click(screen.getByRole("menuitem", { name: "Remove" }));
    await user.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(screen.getByRole("complementary", { name: "Document library" })).toHaveFocus());
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(document.body.querySelector("[inert]")).toBeNull();
  });

  it("switches exclusive mobile panes without remounting content or losing draft/selection/scroll", async () => {
    media("mobile"); const user = userEvent.setup(); render(<Harness />);
    const nav = screen.getByRole("navigation", { name: "Sections" });
    const turnScroll = screen.getByTestId("turn-scroll"); turnScroll.scrollTop = 140;
    const sourceScroll = screen.getByTestId("source-scroll"); sourceScroll.scrollTop = 65;
    const draft = screen.getByRole("textbox", { name: "Question draft" });
    await user.type(draft, " continued");
    await user.click(within(nav).getByRole("button", { name: "Documents" }));
    expect(screen.queryByRole("main")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Sources" })).not.toBeInTheDocument();
    await user.type(screen.getByRole("searchbox"), "Synthetic");
    await user.click(screen.getByRole("checkbox", { name: /Synthetic study/ }));
    const libraryScroll = screen.getByRole("complementary").querySelector<HTMLElement>(".pane-scroll")!;
    libraryScroll.scrollTop = 85; fireEvent.scroll(libraryScroll);
    await user.click(within(nav).getByRole("button", { name: "Sources" }));
    expect(screen.getByRole("region", { name: "Sources" })).toBeVisible();
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    await user.click(within(nav).getByRole("button", { name: "Conversation" }));
    expect(draft).toHaveValue("Preserve this draft continued");
    expect(screen.getByTestId("turn-scroll")).toBe(turnScroll);
    expect(turnScroll.scrollTop).toBe(140); expect(sourceScroll.scrollTop).toBe(65);
    await user.click(within(nav).getByRole("button", { name: "Documents" }));
    expect(screen.getByRole("searchbox")).toHaveValue("Synthetic");
    expect(screen.getByRole("checkbox", { name: /Synthetic study/ })).not.toBeChecked();
    expect(libraryScroll.scrollTop).toBe(85);
    expect(within(nav).getByRole("button", { name: "Documents" })).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps the same library when closing/reopening the drawer and changing layout modes", async () => {
    const change = media("split"); const user = userEvent.setup(); render(<Harness />);
    await user.click(screen.getByRole("button", { name: "Documents" }));
    const library = screen.getByRole("complementary");
    const scroll = library.querySelector<HTMLElement>(".pane-scroll")!; scroll.scrollTop = 70; fireEvent.scroll(scroll);
    await user.type(screen.getByRole("searchbox"), "Synthetic");
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Documents" }));
    expect(screen.getByRole("complementary")).toBe(library);
    expect(scroll.scrollTop).toBe(70);
    change("wide");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("complementary")).toBe(library);
    expect(screen.getByRole("searchbox")).toHaveValue("Synthetic");
    expect(document.body.querySelector("[inert]")).toBeNull();
    change("split"); expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("does not leave the app inert if a breakpoint removes the drawer beneath a dialog", async () => {
    const change = media("split"); const user = userEvent.setup(); render(<Harness />);
    await user.click(screen.getByRole("button", { name: "Documents" }));
    await user.click(screen.getByRole("button", { name: /More actions for/ }));
    await user.click(screen.getByRole("menuitem", { name: "Details" }));
    change("wide"); expect(screen.getAllByRole("dialog")).toHaveLength(1);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.getByRole("button", { name: /More actions for/ })).toHaveFocus());
    expect(document.body.querySelector("[inert]")).toBeNull();
    expect(document.body.style.overflow).not.toBe("hidden");
  });
});
