# evaluation

Reusable metrics and runners over the same `HybridSearchService`, `EvidencePipeline`,
and `RAGService` used in serving.

`EvaluationRunner` is the ragbench path (independent questions).
`QualityEvaluationRunner` is the qualitybench path (follow-up rewrite + answer/citation traces).

Gold evidence is labeled as **filename + passage text**, then resolved to `chunk_id`s
for the chunker under test. That keeps structure vs window comparisons honest.

Unit tests use hashing embeddings, overlap/scripted rerank, and `ScriptedLLM`.
They do not require network, GPU, API keys, or Ollama.

CLI evaluation constructs dedicated storage before opening an Application. The
workspace and report contract are documented in
[the evaluation guide](../../../evaluation/README.md). Both runners report
`evidence-metrics.v2`; selected chunk IDs, exact rendered passages, cited gold
coverage, and lexical claim overlap are separate diagnostics. None is entailment.
