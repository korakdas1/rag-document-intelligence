# Changelog

## 0.10.0 — public snapshot

First public source snapshot of the local RAG research assistant.

- Hybrid dense + BM25 retrieval with RRF and MiniLM reranking
- Grounded generation with citation validation and bounded marker repair
- Persistent research sessions; history rewrites the query, not the evidence
- FastAPI backend, Vite/React workspace, Docker API image (Ollama on the host)
- Synthetic evaluation harness (`ragbench_v1`, `qualitybench_v1`) and offline tests
- MIT License
