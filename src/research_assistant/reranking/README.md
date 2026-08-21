# reranking

Query-time re-scoring of a candidate chunk list.

Implemented: `Reranker` protocol, `CrossEncoderReranker` (development default
`cross-encoder/ms-marco-MiniLM-L-6-v2`), `OverlapReranker` / `ScriptedReranker`
test doubles, `RerankingService`. Optional via `rerank_enabled`. Scores are
ranking logits, not calibrated probabilities.
