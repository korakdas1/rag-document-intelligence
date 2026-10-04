# Evaluation

Benchmarks are **small and synthetic**. They measure retrieval, grounding, citations, abstention, and latency. They are not a claim of general accuracy.

Offline `pytest` uses scripted/hashing doubles and does **not** call Ollama. Runs that need `qwen2.5-coder:7b` are optional and local.

## Suites

| Suite | What it measures |
| --- | --- |
| `ragbench_v1` | Retrieval / context construction on a tiny synthetic corpus |
| `qualitybench_v1` | Answerability, citations, leaks, follow-ups (57 **test** items) |

How to run: [evaluation/README.md](../evaluation/README.md).

## Historical qualitybench_v1 test (n=57)

Historical configuration (local `qwen2.5-coder:7b`, grounded JSON protocol, citation-marker repair on, hybrid retrieval + MiniLM rerank, frozen context budget):

| Metric | Result |
| --- | --- |
| Answerable / unanswerable | 50 / 7 |
| Gold chunk selected (legacy ID diagnostic) | 50/50 answerable |
| Abstention with selected gold chunk (legacy ID diagnostic) | 7/50 |
| False answer on unanswerable | 0/7 |
| Product GROUNDED / UNVERIFIED / insufficient evidence | 35 / 8 / 14 |
| GROUNDED passing the historical lexical audit (not entailment) | 33/35 |
| Citation coverage (answerable, non-abstaining) | 35/43 ≈ 81% |
| Invalid citation IDs | 0 |
| Malformed model output | 0 |
| Leak-control items abstained | 3/3 |
| True conflict reported | 0/1 |

**Do not read 81% as overall answer accuracy.** It is marker coverage among items that needed citations and did not abstain.

These figures predate `evidence-metrics.v2` and have not been regenerated. Chunk selection cannot establish that the required gold text reached generation. The seven abstentions cannot be assigned to generation alone without measuring the rendered excerpts. No new live Ollama run was performed for the metric change.

## Retrieval

The historical hybrid/rerank run selected a gold chunk for every answerable test item (50/50). This is not the new rendered-passage any/all/recall measurement. Dense-only or BM25-only were weaker in earlier retrieval experiments; the serving default is hybrid RRF.

## Grounding and citations

- Missing `[S#]` → **unverified**, not a silent success
- Python does not auto-attach the top-ranked chunk as a citation
- A valid ID is **not** semantic entailment; the historical lexical audit flagged 2 of 35 GROUNDED items (adjacent entity vs asked relation), without establishing semantic support for the others
- Conflicts can collapse to one cited side or abstain instead of reporting disagreement

## Prompt and repair judgment

The serving prompt and citation-repair setting were kept after alternatives increased false abstention, parroting, unsupported claims, or factual drift. A smaller second model used only for marker repair was faster per call but changed facts and contended for GPU memory; it is not the default.

## Latency (one local machine)

Profiling split the request into stages. Warm hybrid retrieval was ~13.5 ms and rerank ~19.4 ms. First-pass generation was ~5.4 s; citation repair, when invoked, ~6.2 s. Warm end-to-end median on that slice ~8.18 s. The first request after process/model start was ~29.6 s. An explicit Ollama keep-alive of 30 minutes did not improve **consecutive** warm requests (already loaded). Hardware differs; these numbers are not a product SLA.

Repair was invoked on 34/57 qualitybench_v1 test items (~60%); 26 of those 34 became GROUNDED and 8 stayed UNVERIFIED.

## Limitations of the benchmark

Synthetic documents, modest n, English-only, one local 7B model. Phrase-equivalent questions can still differ in abstention. Multi-source items can omit a supported limitation that is already in context.

## Current measurement contract

Both CLI runners now report `metrics_schema: evidence-metrics.v2`. See the
[metric definitions and migration table](../evaluation/README.md#metric-contract)
for exact denominators and renamed fields. Old reports are not directly comparable.

Evaluation uses its own SQLite/uploads/index/cache workspace, never the configured
serving stores. Reports record the workspace, dataset byte SHA-256, deterministic
corpus SHA-256, Git commit, and model/index configuration identities. Missing or
incompatible prepared state fails clearly; it never falls back to serving data.

Rendered evidence and cited passage coverage use exact post-budget excerpts and
filename provenance. Full gold coverage does not establish that the answer agrees
with the evidence. Claim overlap is lexical, with conservative explicit polarity
and number checks, not an entailment verifier or general paraphrase assessment.
