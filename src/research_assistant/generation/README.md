# generation

Grounded LLM answers from a `ContextBundle`.

Implemented: `LLMClient` protocol, OpenAI-compatible HTTP client (Ollama/OpenAI),
`ScriptedLLM` test double, `GroundedPromptBuilder` (`build_request`), citation
parser/validator, `GroundedGenerationService`, thin `RAGService`.

Does not query Qdrant, BM25, or SQLite. Does not claim hallucination-free output.
Citation-ID validity is syntactic, not semantic entailment.

Prompt identity: `grounded.answerability.v6`. The sufficiency guidance explicitly
recognizes source-stated negatives, limitations, exclusions, and methods that
directly answer the requested property. Nearby caveats do not erase a direct
answer; missing or merely related information remains insufficient. This shared
system guidance also appears during citation repair; repair-specific instructions
are unchanged. Citation repair default **on**
(`llm_citation_repair`); Python never appends `[S#]`. Diagnostics split
`first_pass_generation_ms` and `repair_ms`. Optional empty-default
`llm_keep_alive` / `llm_repair_model_name` do not change serving defaults unless set.
