# data

Local corpora, derived artifacts, and indexes. **Contents are gitignored** except keep files.

| Directory | Purpose |
| --- | --- |
| `raw/` | Original documents to ingest |
| `processed/` | Parsed text, local SQLite, other derived files |
| `indexes/` | Vector / keyword index files if stored on disk |
| `evaluation/` | Local evaluation indexes and copies. Committed datasets live under `evaluation/` at the repository root |

Do not commit PDFs, model weights, or personal corpora.
