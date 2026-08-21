# ingestion

Local filesystem ingest: validate, detect type, checksum, identity, parser dispatch, persist.

`IngestionService` orchestrates ingest. Call it from tests, CLI, and the HTTP API. Do not put this logic in CLI code. Checksum changes also trigger `VectorIndexInvalidator` (default: registry walker) so stale vectors are not CLI-only.
