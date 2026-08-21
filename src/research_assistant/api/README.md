# Product HTTP API

Thin FastAPI layer over `create_application()`. The UI must not implement RAG.

| Path | Role |
| --- | --- |
| `GET /api/health` | SQLite / Qdrant / LLM availability |
| `GET /api/documents` | Library listing |
| `GET /api/documents/{id}` | Document details |
| `POST /api/documents` | Upload → ingest → chunk → index |
| `POST /api/documents/{id}/reindex` | Re-index from stored source path |
| `DELETE /api/documents/{id}` | Remove indexed metadata, chunks, and vectors (not the original file) |
| `GET /api/sessions` | List research sessions (`updated_at` descending) |
| `POST /api/sessions` | Create an empty session |
| `GET /api/sessions/{id}` | Session metadata, selection, ordered turns |
| `PATCH /api/sessions/{id}` | Rename and/or document selection |
| `DELETE /api/sessions/{id}` | Delete session and turns only (not the document library) |
| `POST /api/ask` | Grounded QA via `RAGService`. Optional `session_id` persists the turn. Without `session_id` the ask is ephemeral. |

Start: `python -m research_assistant serve`
