# configs

Serving hyperparameters live in environment variables / `load_settings()` (see `.env.example`). YAML files in this directory are optional and are not required to run the app.

Defaults (do not change lightly; they match the evaluated configuration):

- Retrieval: hybrid RRF, dense and lexical candidate depth 20, `rrf_k=60`
- Rerank: MiniLM cross-encoder, top 8
- Context budget: 1024 tokens
- Generation: `qwen2.5-coder:7b`, JSON object protocol, citation-marker repair on
