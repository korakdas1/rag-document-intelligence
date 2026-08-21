# evaluation

Reusable metrics and runners over the same `HybridSearchService`, `EvidencePipeline`,
and `RAGService` used in serving.

`EvaluationRunner` is the ragbench path (independent questions).
`QualityEvaluationRunner` is the qualitybench path (follow-up rewrite + answer/citation traces).

Gold evidence is labeled as **filename + passage text**, then resolved to `chunk_id`s
for the chunker under test. That keeps structure vs window comparisons honest.

Unit tests use hashing embeddings, overlap/scripted rerank, and `ScriptedLLM`.
They do not require network, GPU, API keys, or Ollama.
