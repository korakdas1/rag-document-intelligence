# embeddings

`EmbeddingModel` protocol: `embed_documents`, `embed_query`, `identity`.

**Implemented:** local `sentence-transformers` wrapper (default `BAAI/bge-small-en-v1.5`) and a hashing embedder for tests. Query/document prefixes are applied inside the implementation.

Does not store vectors. Does not search.
