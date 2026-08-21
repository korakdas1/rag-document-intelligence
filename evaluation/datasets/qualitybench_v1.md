# qualitybench_v1

Answer/citation quality set. **Does not replace** `ragbench_v1`.

- **Documents:** 8 original synthetic markdown files under `evaluation/corpus/quality/`
- **Questions:** 63 (`dev` 6 / `test` 57)
- **Gold:** filename + verbatim passage, written from the corpus (not from the retriever)
- **Answerability:** explicit `answerable` / `expected_insufficient` labels
- **Splits:** `dev` is for scripted/smoke tests. Reported tables use `test`
- **Slices:** core, conflict, leak, followup, contamination, paraphrase, longdoc, subset
- **License:** project-owned synthetic text

Reference answers and key facts are hints for content metrics. Exact string match is not the primary score.

Do not auto-label gold with the system under test.
