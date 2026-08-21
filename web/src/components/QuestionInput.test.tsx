import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { QuestionInput } from "./QuestionInput";

describe("QuestionInput", () => {
  it("submits the current textarea value once on Enter", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    function Harness() {
      const [value, setValue] = useState("hello");
      return (
        <QuestionInput value={value} disabled={false} onChange={setValue} onSubmit={onSubmit} />
      );
    }
    render(<Harness />);
    await user.click(screen.getByLabelText("Research question"));
    await user.keyboard("{Enter}");
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("hello");
  });

  it("does not submit on Shift+Enter", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <QuestionInput value="hello" disabled={false} onChange={vi.fn()} onSubmit={onSubmit} />,
    );
    await user.click(screen.getByLabelText("Research question"));
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits the Ask question button value once", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <QuestionInput value="from button" disabled={false} onChange={vi.fn()} onSubmit={onSubmit} />,
    );
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("from button");
  });

  it("is not a native HTML form", () => {
    render(
      <QuestionInput value="x" disabled={false} onChange={vi.fn()} onSubmit={vi.fn()} />,
    );
    expect(screen.getByLabelText("Research question").closest("form")).toBeNull();
    expect(screen.getByRole("button", { name: "Ask question" })).toHaveAttribute("type", "button");
  });
});
