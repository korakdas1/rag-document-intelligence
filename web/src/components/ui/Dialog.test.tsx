import { StrictMode, useRef, useState } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Dialog } from "./Dialog";

function Harness({ removeTrigger = false }: { removeTrigger?: boolean }) {
  const [open, setOpen] = useState(false);
  const [removed, setRemoved] = useState(false);
  return <aside aria-label="Library">
    <button>Library fallback</button>
    {!removed && <button onClick={() => setOpen(true)}>Open</button>}
    {open && <Dialog title="Review" onClose={() => setOpen(false)} dismissOnBackdrop backdropTestId="close-backdrop">
      <button onClick={() => { setRemoved(removeTrigger); setOpen(false); }}>Close</button>
    </Dialog>}
  </aside>;
}

describe("Dialog", () => {
  it("associates a modal dialog with its visible title and focuses the first control", () => {
    render(<Dialog title="Review details" onClose={vi.fn()}><button>Close</button></Dialog>);
    const dialog = screen.getByRole("dialog", { name: "Review details" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(document.getElementById(dialog.getAttribute("aria-labelledby")!)).toHaveTextContent("Review details");
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
  });

  it("wraps forward and backward while skipping disabled, hidden and collapsed controls", async () => {
    const user = userEvent.setup();
    render(<Dialog title="Review" onClose={vi.fn()}>
      <button>First</button><button disabled>Disabled</button><input hidden aria-label="Hidden" />
      <fieldset disabled><input aria-label="Disabled fieldset" /></fieldset>
      <details><summary>Advanced</summary><button>Collapsed</button></details>
      <button>Last</button>
    </Dialog>);
    await user.tab();
    expect(screen.getByText("Advanced")).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Last" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "First" })).toHaveFocus();
    await user.tab({ shift: true });
    expect(screen.getByRole("button", { name: "Last" })).toHaveFocus();
  });

  it("keeps one control focused in both directions and rejects external focus", async () => {
    const user = userEvent.setup();
    const { container } = render(<><button data-testid="outside">Outside</button>
      <Dialog title="Review" onClose={vi.fn()}><button>Close</button></Dialog></>);
    const close = screen.getByRole("button", { name: "Close" });
    await user.tab(); await user.tab({ shift: true });
    expect(close).toHaveFocus();
    screen.getByTestId("outside").focus();
    expect(close).toHaveFocus();
    expect(container).toHaveAttribute("inert");
    expect(container).toHaveAttribute("aria-hidden", "true");
  });

  it("focuses the dialog when it has no natural focus targets", async () => {
    const user = userEvent.setup();
    render(<Dialog title="Waiting" onClose={vi.fn()}><p>Please wait</p></Dialog>);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveFocus();
    await user.tab(); await user.tab({ shift: true });
    expect(dialog).toHaveFocus();
  });

  it("recovers focus when busy updates disable every control and uses new enabled controls", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<Dialog title="Remove" onClose={vi.fn()}><button>Cancel</button></Dialog>);
    rerender(<Dialog title="Remove" onClose={vi.fn()} busy><button disabled>Cancel</button></Dialog>);
    await waitFor(() => expect(screen.getByRole("dialog")).toHaveFocus());
    await user.tab();
    expect(screen.getByRole("dialog")).toHaveFocus();
    rerender(<Dialog title="Remove" onClose={vi.fn()}><button>Retry</button></Dialog>);
    await user.tab();
    expect(screen.getByRole("button", { name: "Retry" })).toHaveFocus();
  });

  it("honors explicit safe initial focus and text selection through StrictMode replay", async () => {
    function Rename() {
      const input = useRef<HTMLInputElement>(null);
      return <Dialog title="Rename" onClose={vi.fn()} initialFocusRef={input} selectInitialText>
        <button>Earlier</button><input ref={input} aria-label="Title" defaultValue="Research" />
      </Dialog>;
    }
    render(<StrictMode><Rename /></StrictMode>);
    await act(async () => {});
    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input).toHaveFocus(); expect(input.selectionStart).toBe(0); expect(input.selectionEnd).toBe(8);
  });

  it("restores the actual opener on close", async () => {
    const user = userEvent.setup(); render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open" });
    await user.click(opener); await user.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(opener).toHaveFocus());
  });

  it("restores focus after a pointer backdrop dismissal", async () => {
    const user = userEvent.setup(); render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open" });
    await user.click(opener);
    await user.click(screen.getByTestId("close-backdrop"));
    expect(opener).toHaveFocus();
  });

  it("restores the owning landmark if the opener disappears", async () => {
    const user = userEvent.setup(); render(<Harness removeTrigger />);
    await user.click(screen.getByRole("button", { name: "Open" }));
    await user.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.getByRole("complementary", { name: "Library" })).toHaveFocus());
    expect(screen.getByRole("complementary", { name: "Library" })).toHaveAttribute("tabindex", "-1");
    await user.tab();
    expect(screen.getByRole("complementary", { name: "Library" })).not.toHaveAttribute("tabindex");
  });

  it("dismisses on Escape but not while busy", async () => {
    const user = userEvent.setup(); const onClose = vi.fn();
    const { rerender } = render(<Dialog title="Review" onClose={onClose} busy><button disabled>Wait</button></Dialog>);
    await user.keyboard("{Escape}"); expect(onClose).not.toHaveBeenCalled();
    rerender(<Dialog title="Review" onClose={onClose}><button>Close</button></Dialog>);
    await user.keyboard("{Escape}"); expect(onClose).toHaveBeenCalledOnce();
  });

  it("only dismisses an opted-in backdrop and never an inside click or busy dialog", () => {
    const onClose = vi.fn();
    const content = <button>Inside</button>;
    const { rerender } = render(<Dialog title="Review" onClose={onClose} backdropTestId="backdrop">{content}</Dialog>);
    fireEvent.mouseDown(screen.getByTestId("backdrop")); expect(onClose).not.toHaveBeenCalled();
    rerender(<Dialog title="Review" onClose={onClose} backdropTestId="backdrop" dismissOnBackdrop>{content}</Dialog>);
    fireEvent.mouseDown(screen.getByRole("button")); expect(onClose).not.toHaveBeenCalled();
    fireEvent.mouseDown(screen.getByTestId("backdrop")); expect(onClose).toHaveBeenCalledOnce();
    rerender(<Dialog title="Review" onClose={onClose} backdropTestId="backdrop" dismissOnBackdrop busy>{content}</Dialog>);
    fireEvent.mouseDown(screen.getByTestId("backdrop")); expect(onClose).toHaveBeenCalledOnce();
  });

  it("isolates newly mounted background siblings and restores prior attributes and scroll lock", async () => {
    const existing = document.createElement("div");
    existing.setAttribute("aria-hidden", "false"); existing.setAttribute("inert", "");
    document.body.append(existing); document.body.style.overflow = "clip";
    const { unmount } = render(<Dialog title="Review" onClose={vi.fn()}><button>Close</button></Dialog>);
    const later = document.createElement("button"); document.body.append(later);
    await waitFor(() => expect(later).toHaveAttribute("inert"));
    expect(document.body.style.overflow).toBe("hidden");
    unmount(); await act(async () => {});
    expect(existing).toHaveAttribute("aria-hidden", "false"); expect(existing).toHaveAttribute("inert");
    expect(later).not.toHaveAttribute("inert"); expect(later).not.toHaveAttribute("aria-hidden");
    expect(document.body.style.overflow).toBe("clip");
    existing.remove(); later.remove(); document.body.style.overflow = "";
  });
});
