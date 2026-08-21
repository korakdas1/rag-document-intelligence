import { createEvent, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { useFileDrop } from "./useFileDrop";

function pdfFile(name = "paper.pdf"): File {
  return new File(["%PDF-1.4"], name, { type: "application/pdf" });
}

function fileDrag(files: File[] = [pdfFile()], extra: Record<string, unknown> = {}) {
  return {
    dataTransfer: {
      types: ["Files"],
      files,
      items: files,
      dropEffect: "none",
      effectAllowed: "copy",
    },
    ...extra,
  };
}

function Harness({
  onFiles = () => {},
  enabled = true,
}: {
  onFiles?: (files: File[]) => void;
  enabled?: boolean;
}) {
  const { dropActive, dropBind } = useFileDrop(onFiles, enabled);
  return (
    <div data-testid="drop-root" {...dropBind}>
      <h2>Inner</h2>
      <div
        className={dropActive ? "drop-overlay is-active" : "drop-overlay"}
        data-testid="overlay"
        aria-hidden={!dropActive}
      >
        Drop files to add them
      </div>
    </div>
  );
}

function expectOverlay(visible: boolean) {
  const overlay = screen.getByTestId("overlay");
  if (visible) {
    expect(overlay).toHaveClass("is-active");
    expect(overlay).toHaveAttribute("aria-hidden", "false");
  } else {
    expect(overlay).not.toHaveClass("is-active");
    expect(overlay).toHaveAttribute("aria-hidden", "true");
  }
  expect(screen.getByTestId("drop-root")).toBeInTheDocument();
}

describe("useFileDrop", () => {
  it("shows overlay on dragenter", () => {
    render(<Harness />);
    fireEvent.dragEnter(screen.getByTestId("drop-root"), fileDrag());
    expectOverlay(true);
  });

  it("hides overlay on dragleave", () => {
    render(<Harness />);
    const root = screen.getByTestId("drop-root");
    fireEvent.dragEnter(root, fileDrag());
    expectOverlay(true);
    fireEvent.dragLeave(root, fileDrag());
    expectOverlay(false);
  });

  it("resets when dragleave has empty dataTransfer types", () => {
    render(<Harness />);
    const root = screen.getByTestId("drop-root");
    fireEvent.dragEnter(root, fileDrag());
    expectOverlay(true);
    fireEvent.dragLeave(root, {
      dataTransfer: { types: [], files: [], items: [], dropEffect: "none", effectAllowed: "none" },
    });
    expectOverlay(false);
  });

  it("lets a second drag work after a cancelled drag", () => {
    render(<Harness />);
    const root = screen.getByTestId("drop-root");
    fireEvent.dragEnter(root, fileDrag());
    expectOverlay(true);
    fireEvent.dragLeave(root, fileDrag());
    expectOverlay(false);
    fireEvent.dragEnter(root, fileDrag());
    expectOverlay(true);
  });

  it("claims a follow-up dragover even when types are empty after cancel", () => {
    render(<Harness />);
    const root = screen.getByTestId("drop-root");
    fireEvent.dragEnter(root, fileDrag());
    fireEvent.dragLeave(root, fileDrag());
    expectOverlay(false);
    const over = createEvent.dragOver(window, {
      dataTransfer: {
        types: [],
        files: [],
        items: [],
        dropEffect: "none",
        effectAllowed: "copy",
      },
    });
    fireEvent(window, over);
    expect(over.defaultPrevented).toBe(true);
    fireEvent.dragEnter(root, fileDrag());
    expectOverlay(true);
  });

  it("clears drop lock on cancel so a later drop is accepted", () => {
    const onFiles = vi.fn();
    render(<Harness onFiles={onFiles} />);
    const root = screen.getByTestId("drop-root");
    fireEvent.dragEnter(root, fileDrag());
    fireEvent.dragLeave(root, fileDrag());
    fireEvent.drop(root, fileDrag());
    expect(onFiles).toHaveBeenCalledTimes(1);
    fireEvent.dragEnter(root, fileDrag());
    expectOverlay(true);
  });

  it("resets on window blur and accepts a later drag", () => {
    render(<Harness />);
    fireEvent.dragEnter(screen.getByTestId("drop-root"), fileDrag());
    expectOverlay(true);
    fireEvent.blur(window);
    expectOverlay(false);
    fireEvent.dragEnter(screen.getByTestId("drop-root"), fileDrag());
    expectOverlay(true);
  });

  it("resets when the document becomes hidden", () => {
    render(<Harness />);
    fireEvent.dragEnter(screen.getByTestId("drop-root"), fileDrag());
    expectOverlay(true);
    fireEvent(document, new Event("visibilitychange"));
    expectOverlay(false);
  });

  it("resets on invalid drop so the next drag can start", () => {
    const onFiles = vi.fn();
    render(<Harness onFiles={onFiles} />);
    const root = screen.getByTestId("drop-root");
    fireEvent.dragEnter(root, fileDrag());
    expectOverlay(true);
    fireEvent.drop(
      root,
      fileDrag([new File(["img"], "photo.png", { type: "image/png" })]),
    );
    expectOverlay(false);
    expect(onFiles).toHaveBeenCalledTimes(1);
    fireEvent.dragEnter(root, fileDrag());
    expectOverlay(true);
  });

  it("resets on valid drop", () => {
    const onFiles = vi.fn();
    render(<Harness onFiles={onFiles} />);
    const root = screen.getByTestId("drop-root");
    fireEvent.dragEnter(root, fileDrag());
    fireEvent.drop(root, fileDrag());
    expectOverlay(false);
    expect(onFiles).toHaveBeenCalledTimes(1);
  });

  it("resets on Escape after a drag and accepts a later drag", () => {
    render(<Harness />);
    fireEvent.dragEnter(screen.getByTestId("drop-root"), fileDrag());
    expectOverlay(true);
    fireEvent.keyDown(window, { key: "Escape" });
    expectOverlay(false);
    fireEvent.dragEnter(screen.getByTestId("drop-root"), fileDrag());
    expectOverlay(true);
  });

  it("resets when the drag leaves the document and accepts a later drag", () => {
    render(<Harness />);
    fireEvent.dragEnter(screen.getByTestId("drop-root"), fileDrag());
    expectOverlay(true);
    fireEvent.dragLeave(document.documentElement, fileDrag());
    expectOverlay(false);
    fireEvent.dragEnter(screen.getByTestId("drop-root"), fileDrag());
    expectOverlay(true);
  });

  it("hides overlay after an external cancel leave on a nested target", async () => {
    render(<Harness />);
    const root = screen.getByTestId("drop-root");
    const inner = screen.getByRole("heading", { name: "Inner" });
    fireEvent.dragEnter(root, fileDrag());
    expectOverlay(true);
    fireEvent.dragLeave(inner, fileDrag([], { relatedTarget: null }));
    await waitFor(() => {
      expect(screen.getByTestId("overlay")).not.toHaveClass("is-active");
    });
    fireEvent.dragEnter(root, fileDrag());
    expectOverlay(true);
  });

  it("does not emit files twice for overlapping drop events", () => {
    const onFiles = vi.fn();
    render(<Harness onFiles={onFiles} />);
    const root = screen.getByTestId("drop-root");
    fireEvent.drop(root, fileDrag());
    fireEvent.drop(root, fileDrag());
    expect(onFiles).toHaveBeenCalledTimes(1);
  });

  it("does not flicker on nested dragenter and dragleave", () => {
    render(<Harness />);
    const root = screen.getByTestId("drop-root");
    const inner = screen.getByRole("heading", { name: "Inner" });
    fireEvent.dragEnter(root, fileDrag());
    fireEvent.dragEnter(inner, fileDrag([], { relatedTarget: inner }));
    expectOverlay(true);
    fireEvent.dragLeave(inner, fileDrag([], { relatedTarget: root }));
    expectOverlay(true);
    fireEvent.dragLeave(root, fileDrag());
    expectOverlay(false);
  });

  it("does not replace the drop root when the overlay is shown", () => {
    render(<Harness />);
    const root = screen.getByTestId("drop-root");
    fireEvent.dragEnter(root, fileDrag());
    expect(screen.getByTestId("drop-root")).toBe(root);
    expect(root).toContainElement(screen.getByTestId("overlay"));
    expect(root).toContainElement(screen.getByRole("heading", { name: "Inner" }));
  });
});

describe("useFileDrop enabled toggle", () => {
  function ToggleHarness() {
    const [enabled, setEnabled] = useState(true);
    const { dropActive, dropBind } = useFileDrop(() => {}, enabled);
    return (
      <div data-testid="drop-root" {...dropBind}>
        <button type="button" onClick={() => setEnabled(false)}>
          disable
        </button>
        <div
          className={dropActive ? "drop-overlay is-active" : "drop-overlay"}
          data-testid="overlay"
          aria-hidden={!dropActive}
        >
          Drop files to add them
        </div>
      </div>
    );
  }

  it("clears drag state when the drop target is disabled", () => {
    render(<ToggleHarness />);
    fireEvent.dragEnter(screen.getByTestId("drop-root"), fileDrag());
    expectOverlay(true);
    fireEvent.click(screen.getByRole("button", { name: "disable" }));
    expectOverlay(false);
  });
});
