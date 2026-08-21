# scripts

Helpers that ship with the public repository. They do not change serving defaults.

| Script | Role |
| --- | --- |
| `check_environment.py` | Report config, SQLite, Qdrant, Ollama; does not download or repair |
| `dev.sh` | Start API/UI or `./scripts/dev.sh check` |
| `generate_pdf_fixtures.py` | Regenerates committed PDF test binaries (needs PyMuPDF; **not** a runtime dependency) |
| `build_ragbench_v1.py` | Regenerates `evaluation/datasets/ragbench_v1.jsonl` |
| `eval_followup_resolver.py` | Scores the heuristic follow-up resolver on `ragbench_followup_v1` (no LLM) |
| `eval_generation_citation.py` | Optional local-model citation-protocol check on fixed ContextBundles |
| `eval_generation_implication.py` | Optional implication vs abstention check on fixed ContextBundles |
| `eval_generation_protocol.py` | Optional protocol-reliability check on fixed ContextBundles |
| `eval_answerability.py` | Optional answerability A/B on fixed ContextBundles |
| `eval_subject_citation.py` | Optional subject-completeness / citation check on fixed ContextBundles |
| `trace_retrieval.py` | Trace one stored chunk through dense, BM25, RRF, rerank, and context |

```bash
python -m research_assistant ingest PATH --db data/processed/research_assistant.db
python -m research_assistant serve --host 127.0.0.1 --port 8000
./scripts/dev.sh api
./scripts/dev.sh ui
python scripts/check_environment.py
```
