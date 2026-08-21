import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { DiagnosticsView } from "../api/types";
import { DiagnosticsPanel } from "./DiagnosticsPanel";

const diagnostics: DiagnosticsView = {
  retrieval_mode: "hybrid",
  rerank_enabled: true,
  candidate_count: 2,
  context_source_count: 1,
  dense_ms: 1.2,
  lexical_ms: 0.8,
  fusion_ms: 0.1,
  retrieval_ms: 2,
  rerank_ms: 3,
  generation_ms: 12,
  llm_id: "scripted",
  reranker_id: "overlap",
  validation_status: "missing_citations",
  original_question: "Do they marry?",
  retrieval_query: "Do Harry and Hermione marry?",
  generation_question: "Do Harry and Hermione marry?",
  rewrite_applied: true,
  followup_detected: true,
  resolver_id: "followup.heuristic.v3",
  resolver_method: "pronoun",
  parsed_inline_citation_ids: [],
  validated_citation_ids: [],
  candidates: [
    {
      chunk_id: "c1",
      document_id: "doc-1",
      filename: "very-long-paper-name-for-tooltip.md",
      rank: 1,
      page_start: 13,
      page_end: 13,
      section_path: ["Ending"],
      dense_rank: 1,
      lexical_rank: 2,
      rerank_rank: 1,
      retrievers: ["dense", "lexical"],
      rerank_score: -1.25,
      selected_in_context: true,
      context_position: 1,
      score_note: "logit",
    },
  ],
};

describe("DiagnosticsPanel", () => {
  it("stays collapsed until opened and keeps raw validation status", async () => {
    const user = userEvent.setup();
    render(
      <DiagnosticsPanel
        diagnostics={diagnostics}
        mode="hybrid"
        rerank
        onModeChange={vi.fn()}
        onRerankChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Developer details" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByText("missing_citations")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Developer details" }));
    expect(screen.getByRole("button", { name: "Developer details" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByText("missing_citations")).toBeInTheDocument();
    expect(screen.getAllByText("Do Harry and Hermione marry?").length).toBe(2);
    expect(
      screen.getByText("Rerank scores are uncalibrated logits, not relevance percentages."),
    ).toBeInTheDocument();
    expect(screen.getByTitle("very-long-paper-name-for-tooltip.md")).toBeInTheDocument();
    expect(screen.getByText("Selected (#1)")).toBeInTheDocument();
  });

  it("shows first-pass and citation-repair latency when present", async () => {
    const user = userEvent.setup();
    render(
      <DiagnosticsPanel
        diagnostics={{
          ...diagnostics,
          generation_ms: 9800,
          first_pass_generation_ms: 4500,
          repair_ms: 5300,
          repair_attempts: 1,
        }}
        mode="hybrid"
        rerank
        onModeChange={vi.fn()}
        onRerankChange={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Developer details" }));
    expect(screen.getByText("First-pass latency")).toBeInTheDocument();
    expect(screen.getByText("Citation-repair latency")).toBeInTheDocument();
    expect(screen.getByText("1 attempt")).toBeInTheDocument();
  });
});
