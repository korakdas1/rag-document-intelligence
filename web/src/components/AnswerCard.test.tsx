import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { AskResponse } from "../api/types";
import { AnswerCard } from "./AnswerCard";

function response(overrides: Partial<AskResponse>): AskResponse {
  return {
    question: "What is attention?",
    answer: "Transformers use self-attention [S1].",
    grounding_status: "grounded",
    validation_status: "valid",
    insufficient_evidence: false,
    citations: [
      {
        citation_id: "S1",
        filename: "attention.md",
        document_id: "doc-1",
        page_start: 1,
        page_end: 1,
        section_path: ["Architecture"],
        locator: 'attention.md, p. 1, section "Architecture"',
        occurrence_count: 1,
      },
    ],
    sources: [
      {
        citation_id: "S1",
        filename: "attention.md",
        document_id: "doc-1",
        page_start: 1,
        page_end: 1,
        section_path: ["Architecture"],
        locator: 'attention.md, p. 1, section "Architecture"',
        text: "Self-attention allows each token to attend to every other token.",
        truncated: false,
        cited_by_model: true,
      },
    ],
    diagnostics: {
      retrieval_mode: "hybrid",
      rerank_enabled: true,
      candidate_count: 1,
      context_source_count: 1,
      dense_ms: 1,
      lexical_ms: 1,
      fusion_ms: 1,
      retrieval_ms: 3,
      rerank_ms: 0,
      generation_ms: 10,
      llm_id: "scripted.v1",
      reranker_id: "overlap",
      validation_status: "valid",
      candidates: [],
    },
    request_id: "test",
    ...overrides,
  };
}

describe("AnswerCard", () => {
  it("renders grounded citations as buttons", async () => {
    const user = userEvent.setup();
    const onCitationClick = vi.fn();
    render(
      <AnswerCard
        response={response({})}
        activeCitationId={null}
        onCitationClick={onCitationClick}
      />,
    );
    expect(screen.getByText("Grounded")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "[S1]" }));
    expect(onCitationClick).toHaveBeenCalledWith("S1");
  });

  it("does not present insufficient evidence as a success", () => {
    render(
      <AnswerCard
        response={response({
          answer: "",
          grounding_status: "insufficient_evidence",
          validation_status: "insufficient_evidence",
          insufficient_evidence: true,
          citations: [],
        })}
        activeCitationId={null}
        onCitationClick={vi.fn()}
      />,
    );
    expect(screen.getByText("Not enough evidence")).toBeInTheDocument();
    expect(screen.queryByText("Grounded")).not.toBeInTheDocument();
  });

  it("does not present missing citations as grounded", () => {
    render(
      <AnswerCard
        response={response({
          answer: "Connection refused means the socket was closed.",
          grounding_status: "unverified",
          validation_status: "missing_citations",
          citations: [],
        })}
        activeCitationId={null}
        onCitationClick={vi.fn()}
      />,
    );
    expect(screen.getByText("Unverified")).toBeInTheDocument();
    expect(
      screen.getByText(/could not be fully verified against the retrieved sources/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Connection refused means the socket was closed.")).toBeInTheDocument();
    expect(screen.queryByText("Grounded")).not.toBeInTheDocument();
  });

  it("does not present malformed output as grounded", () => {
    render(
      <AnswerCard
        response={response({
          answer: "",
          grounding_status: "malformed_output",
          validation_status: "malformed_output",
          citations: [],
        })}
        activeCitationId={null}
        onCitationClick={vi.fn()}
      />,
    );
    expect(screen.getByText("Invalid response format")).toBeInTheDocument();
    expect(
      screen.getByText(/invalid response format\. Retrieved evidence is still available/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("Grounded")).not.toBeInTheDocument();
  });
});
