# qualitybench_v2 benchmark card

## Purpose and identity

`qualitybench_v2` is a more realistic synthetic benchmark for future comparative
document-RAG experiments. It exercises provenance, revisions, units, qualifiers,
evidence selection, and answerability in longer, competing documents. It is
additive: `qualitybench_v1` and `ragbench_v1` remain unchanged historical/smaller
suites. Their results are not v2 baselines.

The dataset is [qualitybench_v2.jsonl](qualitybench_v2.jsonl); its corpus is
[quality_v2](../corpus/quality_v2/). The existing `QualityEvaluationRunner` reports
`dataset_id: qualitybench_v2`, `dataset_version: qualitybench.v2`, and
`metrics_schema: evidence-metrics.v2`. Loading v1 still reports `qualitybench.v1`.

**This benchmark is synthetic and project-owned. It is not a claim of real-world
production accuracy.** No live model baseline is published with its construction.

## Corpus structure and ownership

All twenty Markdown documents are original material authored for this repository,
under the repository's [license](../../LICENSE). No papers, company manuals,
news, third-party benchmark text, or confidential records were copied. The people,
projects, events, and measurements are fictional. In particular, numbers inside
the Atlas documents describe a fictional study, not this repository's performance.

The corpus contains **91,910 UTF-8 bytes** (about 89.8 KiB), excluding the dataset
and this card. Size bands use decimal KB: **6 short** documents (1–2 KB),
**10 medium** (2.5–5 KB), and **4 long** (8–12 KB).

| Family | Five documents | Short / medium / long |
| --- | --- | --- |
| Northstar Battery Pilot | brief, protocol, operations report, incident, amendment | 1 / 3 / 1 |
| Meridian Transit Sensor Study | brief, protocol, operations report, incident, release | 2 / 2 / 1 |
| Kestrel Field Station | brief, protocol, operations notebook, incident, amendment | 1 / 3 / 1 |
| Atlas Retrieval Research Program | brief, methods, operations report, limitations, release | 2 / 2 / 1 |

The archive mixes planning prose, formal procedures, checklists, field observations,
incident hypotheses, and signed corrections. Shared terms such as baseline,
sample, validation, sensor, inspection, and release create retrieval competition.
Paragraphs supply evidence, operational context, a plausible distractor, or a
provenance signal. Each family contributes 24 questions: 6 dev and 18 test.

## Examples and distributions

There are **96 examples: 24 dev and 72 test**. Of these, **80 are answerable and
16 unanswerable** (16.7%). Dev contains 20 answerable / 4 unanswerable; test contains
60 answerable / 12 unanswerable. Most missing-answer cases concern an existing
entity's absent attribute or an unmeasured quantity near a measured one. The
clinical-use question is a deliberately out-of-domain leakage check.

Primary categories describe question form. Slices describe the principal
difficulty; secondary tags can overlap both. For example, a subset question can
also ask for an identifier, and a paraphrase can concern a superseded threshold.

| Category | Dev | Test | Total |
| --- | ---: | ---: | ---: |
| comparison | 0 | 5 | 5 |
| conflicting | 0 | 6 | 6 |
| date | 0 | 5 | 5 |
| factual | 1 | 4 | 5 |
| followup | 1 | 6 | 7 |
| identifier | 3 | 0 | 3 |
| insufficient | 4 | 12 | 16 |
| limitation | 1 | 1 | 2 |
| methodology | 2 | 2 | 4 |
| multi_paragraph | 0 | 3 | 3 |
| multi_source | 0 | 2 | 2 |
| named_entity | 1 | 2 | 3 |
| numeric | 5 | 9 | 14 |
| paraphrase | 3 | 6 | 9 |
| relationship | 0 | 2 | 2 |
| subset | 1 | 5 | 6 |
| summarization | 1 | 1 | 2 |
| yes_no | 1 | 1 | 2 |

| Slice | Dev | Test | Total |
| --- | ---: | ---: | ---: |
| conflict | 0 | 6 | 6 |
| core | 8 | 7 | 15 |
| followup | 1 | 6 | 7 |
| hard_negative | 2 | 4 | 6 |
| longdoc | 4 | 16 | 20 |
| multisource | 1 | 5 | 6 |
| paraphrase | 3 | 6 | 9 |
| subset | 1 | 5 | 6 |
| unanswerable | 4 | 12 | 16 |
| versioning | 0 | 5 | 5 |

Every slice has at least two test examples. No primary category exceeds 25% of
the suite. All twenty documents have labeled evidence. The most referenced source,
`meridian_report.md`, occurs in **8/96 examples (8.33%)**; a source is counted at
most once per example. This is below the 20% concentration limit.

Secondary tags are a small vocabulary: `cross_document`, `date`, `hard_negative`,
`identifier`, `long_document`, `multi_claim`, `near_duplicate`, `negation`,
`numeric`, `paraphrase`, `relationship`, `superseded`, and `unit`.

## Difficulty design

- **16 multi-passage examples**, including 12 spanning different files and four
  requiring distant sections of one long document. Cases cover method plus
  limitation, comparisons, source-specific old/new values, and short summaries.
- **6 genuine conflicts**, all in test: Northstar reserve allocation and inspection
  interval; Meridian invalid-ping count and inspection owner; Kestrel restoration
  duration; Atlas audit-pool allocation. Each labels both sources. The sources
  explicitly leave the disagreement unresolved; later notices do not settle it.
- **5 versioning-slice examples** and **16 near-duplicate-tagged examples**. Explicit
  corrections govern current thresholds, a heater-energy unit, and a preliminary
  component diagnosis. Supersession is not labeled as a conflict.
- **6 hard-negative-slice examples** and **27 hard-negative-tagged examples**,
  including in-domain missing answers. The union of the tag and the versioning
  slice covers **32 examples**. Numeric traps distinguish quiet and calibration
  current, milliseconds and seconds, energy prefixes, and unrelated retention
  schedules. Qualifiers distinguish pilot from production, weekday from weekend,
  measured from inferred, and current from retired.
- **20 long-document-slice examples**. Each long document has test gold in its
  early, middle, and late portions, plus one early/late synthesis. Integrity checks
  use character offsets, not invented page numbers.
- **6 selected-document cases** keep every required source inside
  `selected_filenames`. These include historical-only views even when an explicit
  correction exists elsewhere in the corpus.
- **7 follow-ups** contain short, supplied grounded histories and explicit resolver
  inclusion/exclusion hints. Histories identify the intended referent; they are
  not generated by the system being evaluated.
- **3 paraphrase groups of 3**: Northstar storage is wholly dev; Meridian's final
  score and Atlas's retired-source policy are wholly test. Each group shares its
  gold and scope. Unrelated facts are not grouped merely by question wording.

## Construction and gold-label policy

The construction order was authored corpus, explicitly specified questions and
gold, then deterministic validation and manual review. Gold was not selected from
retrieval hits, reranker output, generated answers, or current citations. Every
example was reviewed for answerability, provenance, qualifiers, source authority,
subset feasibility, follow-up referent, and plausible missing-answer distractors.

Gold uses **filename plus verbatim passage text**, never `relevant_chunk_ids`.
The 96 passage labels reference 83 distinct filename/text pairs. Every passage
occurs exactly once in its declared document and is at most 131 characters long.
Claims carry explicit `claim_id`, `text`, `filename`, and `gold_text`; multi-source
claims are attached to their own sources. Unanswerable items have no gold and
explicitly set `expected_insufficient: true`.

All **80 answerable examples** also include hand-authored lexical `key_facts`
derived only from the existing gold/reference truth; the **16 unanswerable examples
have none**. Compact labels preserve required units, qualifiers, and each answer
component, including both sides of all six conflicts. Paraphrase-group members
share identical labels. These support deterministic answer-content diagnostics;
**key facts are not semantic entailment labels**. Substring matching can miss a
correct paraphrase or match words in an incorrect assertion, so interpret these
diagnostics alongside the source evidence.

Concise reference answers help diagnostics; they are not the primary truth.
Token F1 and lexical claim matching do not establish semantic correctness.
The few `forbidden_facts` strings identify dangerous wrong-value substitutions.
The existing substring diagnostic can also flag a correct explanation that
mentions an obsolete value to reject it: review these hits in context, especially
the energy correction and final acceptance gate. They are not automatic proof
that an answer asserted the wrong fact.

## Dev/test protocol and reproducibility

Use dev for future experiments. Keep test as the frozen comparison set. **Test
retrieval or model performance was not used to construct or tune this set.** No
test retrieval/generation run was performed during construction. Deterministic
validation inspected both splits, including source text and chunk resolution.
There is **zero normalized exact gold-passage overlap across dev and test**,
even when ignoring filenames. No paraphrase group crosses the split boundary.

Freeze the dataset/corpus bytes, record the commit and report fingerprints, and
compare configurations on the same examples. Corpus and document families are
shared between splits; exact-gold separation is not document-level or semantic
independence. An error correction needs an explicit dataset revision and must not
silently replace the inputs of an already reported comparison.

## Integrity and offline execution

Run the committed checks from the repository root:

```bash
python -m pytest -s tests/unit/test_qualitybench_v2.py
```

They validate counts, unique questions/IDs, source existence, answerability,
verbatim unique gold, compact spans, claims, subset scope, leakage, paraphrase
groups, difficulty minima, source concentration, size bands, long-document
positions, and v1/v2 version metadata. They also check lexical-label coverage,
compactness, multi-component and conflict coverage, paraphrase consistency,
serialization, and exclusion of execution results from dataset metadata. Direct
metric fixtures verify that each conflict's one-sided answer is detected, without
retrieval or generation. Category and slice counts are printed.
Parsing and default structure chunking produce **141 chunks**; all **21 dev and
75 test passage labels** resolve without retrieval.

The construction smoke prepared an isolated workspace and ran **only 24 dev
examples**, using hashing embeddings, overlap reranking, and `scripted.v1`.
The report carried the dataset/corpus hashes, correct v2 identity, and
`evidence-metrics.v2`. All 20 answerable dev examples resolved through the actual
prepared store; deterministic resolution also covered all 60 answerable test
examples without searching or generating answers for them. Serving storage
remained unchanged. These are execution checks, **not model-quality scores**.
That smoke predates the lexical-label completion and has not been rerun; its
report retains the original dataset fingerprint. The label correction changes
the dataset bytes, with serialization checked by the integrity tests above.

See [execution instructions](../README.md#qualitybench-v2-development-check).
The final live `qwen2.5-coder:7b` test baseline is **NOT RUN** in this benchmark
construction change; it is reserved for a separate measurement after merge.

## Known limitations

This is a modest English-only synthetic collection with four intentionally
coherent families. Its administrative and engineering prose cannot represent the
full diversity of user libraries. It has no scanned/OCR documents, complex layout,
images, multilingual text, or third-party domain validation. Difficulty is
designed, not yet established by a live baseline.

The small dev set does not mirror every test category. Some facts recur within a
split for controlled paraphrase, follow-up, or scope comparisons; these examples
are not independent observations. Exact gold matching can miss valid alternative
evidence or paraphrases, and full labeled coverage does not prove entailment.
Supplied histories do not measure the quality of an earlier generated turn.
Conflicts are unusually explicit about unresolved authority, and some sources
state their missing-data limits directly. These features improve auditability but
can make abstention and conflict handling easier than in messy operational text.
