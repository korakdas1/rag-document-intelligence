import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { UploadFeedback } from "./UploadFeedback";

describe("UploadFeedback", () => {
  it("announces progress and a successful result", () => {
    const props = { onRetry: vi.fn(), onDismiss: vi.fn() };
    const { rerender } = render(
      <UploadFeedback feedback={{ kind: "progress", current: 2, total: 4 }} {...props} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Uploading 2 of 4…");
    rerender(<UploadFeedback feedback={{ kind: "result", added: 4, failures: [] }} {...props} />);
    expect(screen.getByRole("status")).toHaveTextContent("4 documents added.");
  });

  it("shows per-file failures and retries only attempted supported files", async () => {
    const retry = new File(["bad"], "broken.pdf", { type: "application/pdf" });
    const onRetry = vi.fn();
    render(<UploadFeedback feedback={{ kind: "result", added: 1, failures: [
      { filename: "broken.pdf", reason: "The file is not a valid PDF.", retryFile: retry },
      { filename: "photo.png", reason: "Unsupported file type." },
    ] }} onRetry={onRetry} onDismiss={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("1 added · 2 not added");
    expect(screen.getByText("photo.png")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry failed files" }));
    expect(onRetry).toHaveBeenCalledWith([retry]);
  });

  it("does not offer retry when every failure was rejected client-side", async () => {
    const onDismiss = vi.fn();
    render(<UploadFeedback feedback={{ kind: "result", added: 0, failures: [
      { filename: "photo.png", reason: "Unsupported file type." },
    ] }} onRetry={vi.fn()} onDismiss={onDismiss} />);
    expect(screen.queryByRole("button", { name: "Retry failed files" })).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
