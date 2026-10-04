# generation

Grounded LLM answers from a `ContextBundle`.

Implemented: `LLMClient` protocol, OpenAI-compatible HTTP client (Ollama/OpenAI),
`ScriptedLLM` test double, `GroundedPromptBuilder` (`build_request`), citation
parser/validator, `GroundedGenerationService`, thin `RAGService`.

Does not query Qdrant, BM25, or SQLite. Does not claim hallucination-free output.
Citation-ID validity is syntactic, not semantic entailment.

Prompt identity: `grounded.answerability.v5`. Citation repair default **on**
(`llm_citation_repair`); Python never appends `[S#]`. Diagnostics split
`first_pass_generation_ms` and `repair_ms`. Optional empty-default
`llm_keep_alive` / `llm_repair_model_name` do not change serving defaults unless set.

Citation repair uses the separate `citation.insertion_only.v1` protocol. It receives
the exact parsed answer and the same rendered evidence/allowed IDs, with no question,
first-pass system instructions, or raw first-pass JSON. Only marker insertion is
permitted. A deterministic postcondition reconstructs the original character for
character by removing valid markers and optionally adjacent ASCII spaces. It never
normalizes words, punctuation, case, tabs, newlines, or existing whitespace.

Acceptance requires plain JSON, valid inline IDs, at least one marker, an unchanged
false insufficient-evidence flag, and exact content preservation. Any rejected repair
retains the first-pass answer, raw response, and `missing_citations` status. There is
no retry or third call, including when optional format repair already consumed the
second call. Diagnostics expose `repair_attempts`, `citation_repair_accepted`,
`citation_repair_rejection_reason`, `citation_repair_content_preserved`, repair token
counts, and repair latency without adding evidence or rejected answer text.
