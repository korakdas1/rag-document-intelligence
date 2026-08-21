# tests

Offline tests. They use hashing embeddings, overlap/scripted rerank, and `ScriptedLLM`. They do not need CUDA, Hugging Face downloads, a network, a paid API, or Ollama.

```bash
python -m pytest
```

| Path | Role |
| --- | --- |
| `test_project_foundation.py` | Public docs present; package version |
| `unit/` | Parsers, chunkers, retrieval, rerank, context, citations, generation, eval metrics |
| `integration/` | Ingest → index → hybrid search → RAG + FastAPI (`TestClient`, temp dirs) |
| `fixtures/` | Committed txt/md/pdf samples |

Frontend: `npm --prefix web test`.
