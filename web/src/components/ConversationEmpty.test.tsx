import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConversationEmpty } from "./ConversationEmpty";

describe("ConversationEmpty", () => {
  it("has no interactive starter questions", () => {
    render(<ConversationEmpty hasDocuments />);
    expect(screen.getByText("Ask a question about your documents.")).toBeInTheDocument();
    expect(screen.queryByText("Try a question")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
