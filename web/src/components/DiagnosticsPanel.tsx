import { useId, useState } from "react";
import type { DiagnosticsView, RetrievalMode } from "../api/types";

type DiagnosticsPanelProps = {
  diagnostics: DiagnosticsView | null;
  mode: RetrievalMode;
  rerank: boolean;
  onModeChange: (mode: RetrievalMode) => void;
  onRerankChange: (enabled: boolean) => void;
};

function ms(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${value.toFixed(1)} ms`;
}

function location(
  pageStart: number | null,
  pageEnd: number | null,
  sectionPath: string[],
): string {
  const parts: string[] = [];
  if (pageStart !== null) {
    parts.push(
      pageEnd !== null && pageEnd !== pageStart
        ? `pp. ${pageStart}–${pageEnd}`
        : `p. ${pageStart}`,
    );
  }
  if (sectionPath.length) {
    parts.push(sectionPath.join(" › "));
  }
  return parts.join(" · ") || "—";
}

export function DiagnosticsPanel({
  diagnostics,
  mode,
  rerank,
  onModeChange,
  onRerankChange,
}: DiagnosticsPanelProps) {
  const [open, setOpen] = useState(false);
  const modeId = useId();
  return (
    <section className="diagnostics">
      <button
        type="button"
        className="diagnostics-toggle"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        Developer details
      </button>
      {open ? (
        <div className="diag-body">
          <div className="dev-controls">
            <label htmlFor={modeId}>
              Retrieval mode
              <select
                id={modeId}
                value={mode}
                onChange={(event) => onModeChange(event.target.value as RetrievalMode)}
              >
                <option value="hybrid">hybrid (default)</option>
                <option value="dense">dense</option>
                <option value="lexical">lexical</option>
              </select>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={rerank}
                onChange={(event) => onRerankChange(event.target.checked)}
              />
              Cross-encoder rerank (default on; MiniLM did not improve ragbench_v1 ranking)
            </label>
          </div>
          {diagnostics ? (
            <>
              <div className="diag-group">
                <h3>Retrieval</h3>
                <dl>
                  <div>
                    <dt>Mode</dt>
                    <dd>{diagnostics.retrieval_mode}</dd>
                  </div>
                  <div>
                    <dt>Rerank</dt>
                    <dd>{diagnostics.rerank_enabled ? "on" : "off"}</dd>
                  </div>
                  <div>
                    <dt>Candidates</dt>
                    <dd>{diagnostics.candidate_count}</dd>
                  </div>
                  <div>
                    <dt>Context sources</dt>
                    <dd>{diagnostics.context_source_count}</dd>
                  </div>
                  <div>
                    <dt>Dense</dt>
                    <dd>{ms(diagnostics.dense_ms)}</dd>
                  </div>
                  <div>
                    <dt>BM25</dt>
                    <dd>{ms(diagnostics.lexical_ms)}</dd>
                  </div>
                  <div>
                    <dt>Fusion</dt>
                    <dd>{ms(diagnostics.fusion_ms)}</dd>
                  </div>
                  <div>
                    <dt>Rerank latency</dt>
                    <dd>{ms(diagnostics.rerank_ms)}</dd>
                  </div>
                </dl>
              </div>
              <div className="diag-group">
                <h3>Generation</h3>
                <dl>
                  <div>
                    <dt>Latency</dt>
                    <dd>{ms(diagnostics.generation_ms)}</dd>
                  </div>
                  {diagnostics.first_pass_generation_ms != null ? (
                    <div>
                      <dt>First-pass latency</dt>
                      <dd>{ms(diagnostics.first_pass_generation_ms)}</dd>
                    </div>
                  ) : null}
                  {diagnostics.repair_ms != null && diagnostics.repair_ms > 0 ? (
                    <div>
                      <dt>Citation-repair latency</dt>
                      <dd>{ms(diagnostics.repair_ms)}</dd>
                    </div>
                  ) : null}
                  {diagnostics.llm_id ? (
                    <div>
                      <dt>Model</dt>
                      <dd>{diagnostics.llm_id}</dd>
                    </div>
                  ) : null}
                </dl>
              </div>
              {diagnostics.rewrite_applied || diagnostics.followup_detected ? (
                <div className="diag-group">
                  <h3>Resolution</h3>
                  <dl>
                    <div>
                      <dt>Original question</dt>
                      <dd>{diagnostics.original_question || "—"}</dd>
                    </div>
                    <div>
                      <dt>Resolved question</dt>
                      <dd>{diagnostics.retrieval_query || "—"}</dd>
                    </div>
                    <div>
                      <dt>Generation question</dt>
                      <dd>
                        {diagnostics.generation_question || diagnostics.retrieval_query || "—"}
                      </dd>
                    </div>
                    <div>
                      <dt>Resolver</dt>
                      <dd>
                        {diagnostics.resolver_id || "—"} / {diagnostics.resolver_method || "—"}
                      </dd>
                    </div>
                    <div>
                      <dt>Rewrite</dt>
                      <dd>
                        {diagnostics.rewrite_applied ? "applied" : "none"}
                        {diagnostics.history_turns_used
                          ? ` (${diagnostics.history_turns_used} turns)`
                          : ""}
                      </dd>
                    </div>
                    {diagnostics.conversation_subjects &&
                    diagnostics.conversation_subjects.length ? (
                      <div>
                        <dt>Subjects</dt>
                        <dd>{diagnostics.conversation_subjects.join(", ")}</dd>
                      </div>
                    ) : null}
                  </dl>
                </div>
              ) : null}
              <div className="diag-group">
                <h3>Citations</h3>
                <dl>
                  <div>
                    <dt>Validation</dt>
                    <dd>{diagnostics.validation_status}</dd>
                  </div>
                  <div>
                    <dt>Insufficient evidence</dt>
                    <dd>{diagnostics.insufficient_evidence ? "yes" : "no"}</dd>
                  </div>
                  {diagnostics.context_citation_ids &&
                  diagnostics.context_citation_ids.length ? (
                    <div>
                      <dt>Context citations</dt>
                      <dd>{diagnostics.context_citation_ids.join(", ")}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt>Parsed inline citations</dt>
                    <dd>
                      {(diagnostics.parsed_inline_citation_ids || []).join(", ") || "none"}
                    </dd>
                  </div>
                  <div>
                    <dt>Validated citations</dt>
                    <dd>
                      {(diagnostics.validated_citation_ids || []).join(", ") || "none"}
                    </dd>
                  </div>
                  {diagnostics.structured_citation_ids &&
                  diagnostics.structured_citation_ids.length ? (
                    <div>
                      <dt>Structured citation field</dt>
                      <dd>{diagnostics.structured_citation_ids.join(", ")}</dd>
                    </div>
                  ) : null}
                  {diagnostics.repair_attempts ? (
                    <div>
                      <dt>Citation repair</dt>
                      <dd>{diagnostics.repair_attempts} attempt</dd>
                    </div>
                  ) : null}
                  {diagnostics.generation_protocol_status ? (
                    <div>
                      <dt>Protocol status</dt>
                      <dd>{diagnostics.generation_protocol_status}</dd>
                    </div>
                  ) : null}
                  {diagnostics.raw_output_category ? (
                    <div>
                      <dt>Raw output category</dt>
                      <dd>{diagnostics.raw_output_category}</dd>
                    </div>
                  ) : null}
                  {diagnostics.normalization_applied &&
                  diagnostics.normalization_applied.length ? (
                    <div>
                      <dt>Normalization</dt>
                      <dd>{diagnostics.normalization_applied.join(", ")}</dd>
                    </div>
                  ) : null}
                  {diagnostics.format_repair_attempted ? (
                    <div>
                      <dt>Format repair</dt>
                      <dd>{diagnostics.format_repair_succeeded ? "succeeded" : "attempted"}</dd>
                    </div>
                  ) : null}
                </dl>
              </div>
              <div className="diag-group">
                <h3>Rerank table</h3>
                <p className="hint">
                  Rerank scores are uncalibrated logits, not relevance percentages.
                </p>
                <div className="table-wrap">
                  <table className="diag-table">
                    <thead>
                      <tr>
                        <th>File</th>
                        <th>Location</th>
                        <th className="num">Dense</th>
                        <th className="num">BM25</th>
                        <th className="num">Rerank</th>
                        <th>Context</th>
                        <th className="num">Logit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {diagnostics.candidates.map((hit) => (
                        <tr
                          key={hit.chunk_id}
                          className={hit.selected_in_context ? "selected" : undefined}
                        >
                          <td
                            className="file"
                            title={hit.filename || hit.chunk_id}
                          >
                            {hit.filename || hit.chunk_id.slice(0, 8)}
                          </td>
                          <td>{location(hit.page_start, hit.page_end, hit.section_path)}</td>
                          <td className="num">{hit.dense_rank ?? "—"}</td>
                          <td className="num">{hit.lexical_rank ?? "—"}</td>
                          <td className="num">{hit.rerank_rank ?? hit.rank}</td>
                          <td>
                            {hit.selected_in_context
                              ? `Selected (#${hit.context_position})`
                              : "—"}
                          </td>
                          <td className="num">
                            {hit.rerank_score === null ? "—" : hit.rerank_score.toFixed(3)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <p className="hint">Ask a question to inspect retrieval and citation diagnostics.</p>
          )}
        </div>
      ) : null}
    </section>
  );
}
