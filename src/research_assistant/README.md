# `research_assistant` package map

First-party RAG orchestration: ingest through grounded generation, evaluation, a FastAPI product API, and session-scoped follow-up rewriting. History is not evidence. The Vite UI lives in `web/` and is not part of this package.

| Module | Status |
| --- | --- |
| `core/` | Settings, errors, shared types |
| `ingestion/` | Filesystem ingest service |
| `parsing/` | TXT / Markdown / PDF parsers |
| `chunking/` | Structure-aware + window chunkers |
| `storage/` | SQLite documents, chunks, vector-index catalog |
| `embeddings/` | `EmbeddingModel` (BGE-small + hashing tests) |
| `indexing/` | Qdrant local store, `IndexingService`, `VectorIndexInvalidator` |
| `retrieval/` | Dense, BM25 lexical, metadata filters, hybrid RRF, evidence pipeline |
| `reranking/` | Cross-encoder + test doubles |
| `context/` | Citation-aware context builder |
| `conversation/` | Follow-up QueryResolver (history is not evidence) |
| `generation/` | Grounded generation from `ContextBundle` |
| `evaluation/` | Metrics, ragbench loader, EvaluationRunner |
| `api/` | FastAPI DTOs and routes over `create_application()` |
