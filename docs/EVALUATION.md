# Evaluation

Benchmarks are **small and synthetic**. They measure retrieval, grounding, citations, abstention, and latency. They are not a claim of general accuracy.

Offline `pytest` uses scripted/hashing doubles and does **not** call Ollama. Runs that need `qwen2.5-coder:7b` are optional and local.

## Suites

| Suite | What it measures |
| --- | --- |
| `ragbench_v1` | Retrieval / context construction on a tiny synthetic corpus |
| `qualitybench_v1` | Answerability, citations, leaks, follow-ups (57 **test** items) |

How to run: [evaluation/README.md](../evaluation/README.md).

## qualitybench_v1 test (n=57)

Current production configuration (local `qwen2.5-coder:7b`, grounded JSON protocol, citation-marker repair on, hybrid retrieval + MiniLM rerank, frozen context budget):

| Metric | Result |
| --- | --- |
| Answerable / unanswerable | 50 / 7 |
| Gold chunk reached ContextBundle | 50/50 answerable |
| False abstention with gold in context | 7/50 |
| False answer on unanswerable | 0/7 |
| Product GROUNDED / UNVERIFIED / insufficient evidence | 35 / 8 / 14 |
| Semantically supported GROUNDED (lexical project audit) | 33/35 |
| Citation coverage (answerable, non-abstaining) | 35/43 ≈ 81% |
| Invalid citation IDs | 0 |
| Malformed model output | 0 |
| Leak-control items abstained | 3/3 |
| True conflict reported | 0/1 |

**Do not read 81% as overall answer accuracy.** It is marker coverage among items that needed citations and did not abstain.

Gold-in-context false abstentions remain a generation limitation, not a retrieval miss on those 7 items.

## Retrieval

On this benchmark, hybrid retrieval plus rerank placed gold in the context bundle for every answerable test item (50/50). Dense-only or BM25-only were weaker in earlier retrieval experiments; the serving default is hybrid RRF.

## Grounding and citations

- Missing `[S#]` → **unverified**, not a silent success
- Python does not auto-attach the top-ranked chunk as a citation
- A valid ID is **not** semantic entailment; 2 of 35 GROUNDED items failed a lexical support audit (adjacent entity vs asked relation)
- Conflicts can collapse to one cited side or abstain instead of reporting disagreement

## Prompt and repair judgment

The serving prompt and citation-repair setting were kept after alternatives increased false abstention, parroting, unsupported claims, or factual drift. A smaller second model used only for marker repair was faster per call but changed facts and contended for GPU memory; it is not the default.

## Latency (one local machine)

Profiling split the request into stages. Warm hybrid retrieval was ~13.5 ms and rerank ~19.4 ms. First-pass generation was ~5.4 s; citation repair, when invoked, ~6.2 s. Warm end-to-end median on that slice ~8.18 s. The first request after process/model start was ~29.6 s. An explicit Ollama keep-alive of 30 minutes did not improve **consecutive** warm requests (already loaded). Hardware differs; these numbers are not a product SLA.

Repair was invoked on 34/57 qualitybench_v1 test items (~60%); 26 of those 34 became GROUNDED and 8 stayed UNVERIFIED.

## Limitations of the benchmark

Synthetic documents, modest n, English-only, one local 7B model. Phrase-equivalent questions can still differ in abstention. Multi-source items can omit a supported limitation that is already in context.
