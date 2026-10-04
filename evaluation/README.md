# Evaluation

Small, synthetic, project-owned benchmarks measure retrieval, exact evidence,
citation markers, lexical answer diagnostics, abstention, and latency. They do not
measure general accuracy or semantic entailment. Offline tests use hashing
embeddings, overlap reranking, and scripted generation; no GPU or Ollama is needed.

## Suites

| Suite | Dataset | Corpus |
| --- | --- | --- |
| ragbench | `datasets/ragbench_v1.jsonl` | `corpus/` (top-level documents) |
| qualitybench v1 (historical/smaller) | `datasets/qualitybench_v1.jsonl` | `corpus/quality/` |
| qualitybench v2 | `datasets/qualitybench_v2.jsonl` | `corpus/quality_v2/` |
| Follow-up resolver | `datasets/ragbench_followup_v1.jsonl` | No generation |

The fixed-context genbench scripts are separate optional experiments. Dataset notes:
[datasets/README.md](datasets/README.md). Do not place user uploads in benchmark corpora.

## Qualitybench v2 development check

The [v2 benchmark card](datasets/qualitybench_v2.md) documents the harder synthetic
corpus, distributions, gold policy, and limitations. Keep v1 inputs and historical
results unchanged. For an offline **dev-only** pipeline check:

```bash
python -m pytest -s tests/unit/test_qualitybench_v2.py
RESEARCH_ASSISTANT_LLM_PROVIDER=scripted python -m research_assistant evaluate \
  --dataset evaluation/datasets/qualitybench_v2.jsonl \
  --corpus evaluation/corpus/quality_v2 \
  --workspace evaluation/workspaces/qualitybench_v2_offline_smoke \
  --prepare --stage full --split dev \
  --embedding-model hashing --reranker overlap --llm-model scripted.v1
```

This checks preparation, isolated persistence, gold resolution, and report
serialization. Scripted outputs are not a model-performance baseline. Reports
identify `qualitybench_v2` / `qualitybench.v2` and retain `evidence-metrics.v2`.
The integrity test resolves both splits without retrieval; the command evaluates
only dev. Do not use held-out retrieval or generation results to rewrite test
questions or gold. The [frozen v2 baseline](baselines/qualitybench_v2_baseline_v1.md)
records the separate live test measurement and rules for future comparisons.
A [DEV generation diagnosis](diagnostics/qualitybench_v2_dev_generation_diagnosis_v1.md)
records one unchanged-defaults DEV run, manual failure/repair analysis, and one
unimplemented next experiment. It does not rerun or replace the frozen baseline.
The [single-run sufficiency experiment](experiments/qualitybench_v2_dev_sufficiency_v6.md)
records the v6 DEV comparison and its rejection for factual and citation guardrail failures.
The candidate was not promoted; production remains on `grounded.answerability.v5`.
A future live run needs a separate workspace when the embedding configuration differs.

## Isolated workspace

Run from the repository root:

```bash
python -m research_assistant evaluate \
  --dataset evaluation/datasets/ragbench_v1.jsonl \
  --corpus evaluation/corpus \
  --prepare --stage full \
  --embedding-model hashing --reranker overlap --llm-model scripted.v1
```

The CLI loads normal model/retrieval settings, then constructs an application with
only database, upload, and vector paths replaced. Defaults are:

```text
evaluation/workspaces/<dataset-stem>/
  research_assistant.db
  uploads/
  indexes/qdrant/
  cache/
  workspace.json
```

Use `--workspace PATH` for another dedicated directory. `--db` and `--index-path`
are rejected for evaluation. Paths overlapping configured serving storage, default
`data/processed`, `data/indexes`, `data/uploads`, or corpus files are rejected,
including resolved aliases. Existing non-empty directories without a workspace
manifest and symlinks inside a workspace are refused. No cleanup/delete option is
provided. Shared model-weight download caches are unchanged; `cache/` holds generic
runner generation responses, not model weights. `--cache-dir`, if supplied, must
be `<workspace>/cache` or a descendant; the quality runner does not cache generation.

`--prepare` ingests/chunks/indexes only in that workspace. Omit it to reuse prepared
state. A manifest checks dataset/corpus hashes, chunker, embedding configuration,
and index readiness. Missing/incomplete state requires `--prepare`. Changed input
identity requires a new workspace, preserving the old one. Concurrent use of the
same embedded workspace is not supported. Low-level Python runners accept a
caller-owned Application; programmatic callers must supply isolated storage.

JSON reports stay under ignored `evaluation/results/` unless `--output` is given.
Report output must be outside the workspace (and not an ancestor of it), or under
the dedicated `<workspace>/results` subtree. The workspace database, `indexes/`,
`uploads/`, `cache/`, and `workspace.json` are reserved runtime paths: report output
cannot overlap them. Unsafe explicit cache/output paths are rejected before any
workspace writes; they are never redirected.
The default workspace tree is also ignored. Custom workspace/output paths remain
the caller's responsibility to exclude from version control.

## Metric contract

Both evaluation CLI runners produce **`metrics_schema: evidence-metrics.v2`**.
Per-example JSON retains labeled gold passages, chunk diagnostics, and exact
context/cited excerpts with citation ID, chunk ID, document ID, filename, and
truncation flag. Evidence metrics never reread the full SQLite chunk.

| Field | Definition |
| --- | --- |
| `gold_chunk_selected` | Any resolved gold chunk ID belongs to selected context items; an ID diagnostic only |
| `gold_chunk_rank_context` (quality runner) | One-based position of the first selected gold chunk ID, or null if absent |
| `rerank_gold_passage_hits` | Gold passage presence in full reranked candidate text, before context budget fitting |
| `context_gold_chunk_recall` | Fraction of resolved gold chunk IDs selected, including alternative matching chunks |
| `rendered_gold_passage_hits` | One boolean per labeled gold passage, in label order |
| `rendered_gold_any` | At least one labeled passage is present in the exact rendered excerpts |
| `rendered_gold_all` | Every labeled passage is present; partial multi-source evidence is insufficient |
| `rendered_gold_passage_recall` | Number of present labeled passages divided by number of labeled passages |
| `cited_gold_*` | The same passage metrics, restricted to valid cited excerpts from the current context |
| `cited_gold_coverage_class` | `FULL_GOLD_PASSAGE_COVERAGE`, `PARTIAL_GOLD_PASSAGE_COVERAGE`, `NO_GOLD_PASSAGE_COVERAGE`, or `NOT_APPLICABLE` |
| `citation_id_valid_answer_rate` (generic runner) | Fraction of answers with any cited/invalid IDs that cite only valid IDs; no-marker answers are excluded |
| `lexical_claim_overlap` | Per-marker claim span token overlap, with conservative explicit polarity and number checks |
| `lexical_key_fact_recall` | Fraction of nonempty key-fact labels appearing as normalized substrings in the answer |
| `claim_slots[].lexical_answer_match` | The slot label appears as a normalized substring in the answer |
| `claim_slots[].cited_gold_overlap` | Slot gold text occurs in a cited excerpt from the slot's filename; null if provenance/label is absent |

Passage matching case-folds and collapses whitespace, preserving punctuation. A
whole passage must occur inside one excerpt from the correct filename. Excerpts
are not concatenated across gaps. Empty context yields false/false/0 for labeled
answerable examples. No passage labels or an unanswerable example yields null
any/all/recall and an empty hit list. Unrun stages stay absent/null. Aggregate
rates/recalls are macro means over applicable examples, excluding nulls. Cited
recall includes zero for labeled examples with generation but no valid citations.

`CONTEXT_BUDGET_DROP` requires a passage present in reranked candidate text but
absent from rendered excerpts, including complete context omission.
`FALSE_ABSTENTION_WITH_GOLD_CONTEXT` requires **all** labeled passages actually
rendered. Chunk membership alone never establishes either condition. Generic
`FALSE_ABSTENTION` still records abstention on an answerable example independently
of where the evidence was lost.

Citation-ID validity and product `GROUNDED` remain separate from gold coverage and
claim overlap. `product_grounded_with_full_cited_gold` counts product GROUNDED
outputs whose cited excerpts contain every gold passage; it does not certify the
answer. `product_grounded_without_cited_gold` means no labeled passage was covered,
not that every possible claim is unsupported. `CITED_GOLD_ABSENT` has the same
restricted meaning. Lexical key facts/slots do not measure paraphrase completeness.

Claim labels are `FULL_LEXICAL_OVERLAP`, `PARTIAL_LEXICAL_OVERLAP`,
`NO_LEXICAL_OVERLAP`, `POLARITY_MISMATCH`, and `UNCLEAR`. Polarity-bearing words such
as not/no/never/cannot/denied/rejected are retained. Relevant positive and negative
sentences yield `UNCLEAR`; explicit mismatches cannot get full overlap. Missing
concrete numbers also prevent full overlap. This small English heuristic does not
resolve negation scope, implicit contradictions, double negatives, or entailment.

### Migration from old reports

| Removed/old report field | Current field or interpretation |
| --- | --- |
| `gold_in_context`, `context_gold_hit` | `gold_chunk_selected` (old ID semantics); use `rendered_gold_*` for evidence |
| `context_evidence_recall` | `context_gold_chunk_recall` (old ID semantics) |
| `lexical_citation_support` | Replaced by `cited_gold_passage_recall`; both evidence and denominator changed |
| `semantically_supported_grounded` | Removed; `product_grounded_with_full_cited_gold` makes a narrower, different claim |
| `support_class`, `semantic_support` | `cited_gold_coverage_class`, `cited_gold_coverage` |
| `valid_citation_rate` (generic runner) | `citation_id_valid_answer_rate`; no-marker answers no longer count as valid citations |
| `key_fact_recall`, slot `answered` | `lexical_key_fact_recall`, `lexical_answer_match` |
| `omitted_supported_slots` | `unmatched_labeled_slots` |

The deprecated Python `classify_cited_support` text-only adapter and its old
constant aliases remain only for old offline scripts, emit a deprecation warning,
and return coverage labels. They lack filename provenance and are never used by
new reports. New code uses provenance-aware `classify_cited_gold_coverage`.

## Reproducibility and caches

Reports include Git commit, configuration/index/model identities, workspace path,
`dataset_sha256` (JSONL bytes), and `corpus_sha256`. Corpus identity hashes the
sorted pairs of top-level `.md`/`.txt`/`.pdf` filenames and their byte SHA-256 values,
matching preparation's file set. It excludes mtimes, absolute paths, nested files,
and runtime artifacts; computed once per CLI run. In-memory dataset fixtures use
canonical example JSON and explicitly report `dataset_hash_kind` instead.
Programmatic runners without corpus metadata report a null corpus digest.

The generic generation cache retains its existing question/model/rendered-context
key. Cached answer markers are mapped onto current excerpts; all metrics are
recomputed. Old cached metric fields and old chunk provenance are not trusted.
No model call is added for evidence measurement. The existing optional `--judge`
remains opt-in; these deterministic metrics do not use it.

## Validation and optional live evaluation

```bash
python -m pytest
python -m compileall -q src tests scripts evaluation
```

For a live qualitybench run, use its dataset/corpus paths above, remove the three
offline model flags, and keep the isolated workspace. Ollama with
`qwen2.5-coder:7b` and embedding/reranker weights may require substantial runtime.
Record the exact configuration before comparing runs.

No live run was performed for this metric change. Published 50/50 context results
are historical **chunk-selection** counts; the old lexical audit was not semantic
support. Historical generation numbers remain unchanged and are not reinterpreted
as the new metrics. See [historical results and limitations](../docs/EVALUATION.md).
