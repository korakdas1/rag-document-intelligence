# ragbench_v1

Small committed retrieval benchmark. **Not** a public leaderboard dataset.

- **Documents:** 13 original synthetic markdown notes under `evaluation/corpus/` (top-level files only)
- **Questions:** 47 (`dev` 12, `test` 35)
- **Gold:** filename + verbatim passage text, written by hand from the corpus.
  Chunk IDs are resolved at eval time for the chunker under test so structure vs
  window comparisons stay valid.
- **Splits:** `dev` is for candidate-depth / budget inspection only. Reported
  tables use `test`.
- **License:** project-owned synthetic text. No third-party papers.

Do not auto-label gold with the retriever being evaluated.

# qualitybench_v1

Answer/citation quality set. Lives under `evaluation/corpus/quality/` so it is **not** mixed into ragbench_v1 `prepare_corpus` of the top-level corpus directory. See `qualitybench_v1.md`.

This is the curated public quality suite (test **n=57**).

# qualitybench_phrase_extra

Three `dev` paraphrase items against the same quality corpus. Used by offline pytest. Not mixed into the qualitybench_v1 **test** n=57 table.

# ragbench_followup_v1

Conversational rewrite set (`evaluation/datasets/ragbench_followup_v1.jsonl`). The follow-up narrative lives under `evaluation/corpus/followup/` so it is **not** ingested by ragbench_v1 `prepare_corpus`. Offline pytest scores the heuristic resolver against this file.

# genbench_* (fixed ContextBundles)

Optional local-model checks used by `scripts/eval_generation_*.py` and related helpers. They are not retrieval benchmarks and are not part of CI.
