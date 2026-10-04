# qualitybench_v2 DEV generation diagnosis

## Identity

This is one diagnostic run on all 24 DEV examples, using unchanged production
defaults. It is not a held-out benchmark claim.
The analysis reviewed all 123 rendered evidence blocks, all final answers,
and all 13 saved first-pass/repair pairs; this was not independent human
adjudication.
The [machine-readable diagnosis](qualitybench_v2_dev_generation_diagnosis_v1.json)
records every DEV question, resolver input/output, bounded exact evidence excerpts,
answer, citation, deterministic metric, repair comparison, and analytical judgment.

| Identity | Value |
| --- | --- |
| Source main | `e494fd685c31363aaffc6555a1ef064f5f01dc00` |
| Source post-merge CI | [37183151468](https://github.com/korakdas1/rag-document-intelligence/actions/runs/37183151468), push, completed successfully |
| Analysis branch | `eval/qualitybench-v2-dev-generation-diagnosis` |
| DEV run | `eval_20261004T092610Z_7e617cae80ec` |
| Raw report SHA-256 | `befd206e7ff5b6d18f2e7672710a4f2f59b434ff5ca11482b778bf6e2bde2aa1` |
| Dataset identity | `qualitybench_v2` / `qualitybench.v2` |
| Dataset file SHA-256 | `4ae148bb8c375d667e1803e72ce977431e5b54cf250122ceeaa5d7fde3ddcc9f` |
| Corpus SHA-256 | `c9f92ea09c75cb2976201933c0f044be6b82a66491cc50b00d3783d2ea2f67cb` |
| Metric schema | `evidence-metrics.v2` |
| Execution UTC | 2026-10-04 09:26:01–09:29:54; 233.154 seconds including preparation |

The 446,360-byte raw report remains ignored locally at
`evaluation/results/qualitybench_v2_dev_generation_diagnosis/eval_20261004T092610Z_7e617cae80ec.json`.
It is not committed. The new isolated workspace is
`evaluation/workspaces/qualitybench_v2_dev_generation_diagnosis/`.
Preparation indexed 141 chunks from 20 documents. The JSON records byte hashes
for the dataset, benchmark card, all corpus documents, and both frozen baseline
artifacts. No held-out retrieval or generation was run, and no frozen baseline
was regenerated or used to select a prompt.

## Configuration

Resolved settings were compared with defaults after removing application
environment aliases. There were no application overrides. Only database, index,
and upload storage moved into the evaluation workspace. The JSON preserves the
complete resolved serving settings and isolated path overrides.

| Component | Actual configuration |
| --- | --- |
| Embedding | `BAAI/bge-small-en-v1.5`, normalized, dimension 384, cosine, batch 32, auto device using CUDA |
| Embedding identity | `bge-small-en-v1.5:73115d06b057`; revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` |
| Chunker | `structure.v1:fc9ff956df32`; default target/max/min/overlap 1000/1500/200/150 |
| Retrieval | Hybrid BGE + BM25; dense/lexical candidates 20/20; BM25 k1=1.2, b=0.75; RRF k=60 |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2`; identity `ms-marco-MiniLM-L-6-v2:603b5a7fd2cf`; enabled, 20 candidates, top 8, batch 8, max length 512, CUDA |
| Context | 1024-token budget |
| LLM | Local Ollama 0.21.0, `qwen2.5-coder:7b`, identity `qwen2.5-coder-7b:8f6776b6b431`; 7.6B, Q4_K_M |
| LLM digest | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |
| Generation | OpenAI-compatible local endpoint; temperature 0; max output 512; timeout 120 seconds; `json_object` |
| Prompt / parser / resolver | `grounded.answerability.v5` / `json.object.v2` / `followup.heuristic.v4` |
| Repair | Citation repair enabled, at most one pass, same model; format repair disabled |
| Conversation | Window 4; resolved retrieval query also supplied as generation question |
| Execution | Python 3.13.12; RTX 3050 Laptop GPU, 4096 MiB; no judge, model substitutes, or generation cache |

The reranker reports its model name as its revision; a pinned weight revision is
not available from that identity. Python package versions are preserved in JSON.
The only execution environment additions were `PYTHONPATH=src` and
`HF_HUB_OFFLINE=1`, using already available model weights.

Recorded invocation, already completed once with exit status 0:

```bash
python -m research_assistant evaluate \
  --dataset evaluation/datasets/qualitybench_v2.jsonl \
  --corpus evaluation/corpus/quality_v2 \
  --workspace evaluation/workspaces/qualitybench_v2_dev_generation_diagnosis \
  --prepare --stage full --split dev --mode hybrid \
  --output evaluation/results/qualitybench_v2_dev_generation_diagnosis
```

## DEV run summary

| Measure | Observed result |
| --- | --- |
| Examples | 24: 20 answerable, 4 unanswerable |
| Product status | 17 `GROUNDED`, 7 `NOT_ENOUGH_EVIDENCE`; zero other statuses |
| Gold in hybrid / rerank / selected context | Each 20/20; rate 1.0 |
| Context gold chunk recall | 1.0 |
| Rendered gold any / all / passage recall | Each 1.0 on answerable items |
| Abstention confusion matrix | TP=4, FP=3, FN=0, TN=17; abstention is the positive class |
| Abstention precision / recall | 4/7 = 0.571429 / 4/4 = 1.0 |
| False answer / false abstention rate | 0/4 = 0 / 3/20 = 0.15 |
| False abstentions with all gold rendered | 3 |
| Lexical key-fact recall / all facts matched | 0.70 / 0.70, macro means over 20 answerable items |
| Reference-token F1 diagnostic | 0.286134; not a correctness score |
| Final citation coverage | 17/17 substantive answers = 1.0 |
| Final missing / invalid citations / malformed outputs | 0 / 0 / 0 |
| Cited-gold passage recall | 0.85 across 20 answerable items, including zero for abstentions |
| Grounded with full cited gold / without cited gold | 17 / 0; evidence coverage, not an entailment certificate |
| Repair invocation | 13/24 = 54.17%; 37 total LLM calls, mean 1.541667 |
| Multi-source | One item, two slots; 0/2 lexical matches and 0/2 cited; full abstention |
| Paraphrase stability | One three-item group; stable status and lexical recall |
| Conflict questions | 0; conflict success is not measurable here |

Manual final-content review finds 17 correct answers, four correct abstentions,
and three false abstentions. These are descriptive judgments on this small DEV
sample, separate from the unchanged deterministic scores.

| Latency (ms) | Mean | Median | p95 |
| --- | ---: | ---: | ---: |
| Retrieval | 28.98 | 28.46 | 35.50 |
| Rerank | 38.08 | 38.95 | 42.15 |
| First-pass generation | 5677.34 | 5488.09 | 6575.56 |
| Repair, including zero for unrepaired rows | 3447.59 | 5810.01 | 6890.05 |
| Total generation | 9124.94 | 11081.72 | 12962.86 |
| Total row | 9191.99 | 11150.92 | 13041.08 |

These are the raw runner's timers and percentile definitions, not a controlled
hardware benchmark. Overall wall time additionally includes preparation and
other orchestration work. Aggregates and slice reports were independently
recomputed from the saved DEV rows and matched the raw report exactly.

## Failure counts

The unchanged evaluator reports three `FALSE_ABSTENTION_WITH_GOLD_CONTEXT`
(`qb2-026`, `qb2-028`, `qb2-074`) and three `WRONG_ANSWER`
(`qb2-025`, `qb2-052`, `qb2-076`). All secondary-failure lists are empty.
No `INCOMPLETE_ANSWER`, `MULTISOURCE_SYNTHESIS_FAILURE`, or
`CONFLICT_HANDLING_FAILURE` was emitted. The three apparent wrong answers are
lexical false negatives after manual inspection; no non-abstaining wrong or
incomplete answer was observed.

## Manual diagnostic buckets

Assign one primary analysis bucket to each suspicious row: C for a substantive
false abstention, K for an otherwise correct answer misclassified by lexical
matching, otherwise I for a repaired first-pass citation defect. Null means no
observed defect. Repair observations remain recorded on K rows without counting
them twice. These labels do not change the evaluator taxonomy.

| Bucket | Count |
| --- | ---: |
| C. FALSE_ABSTENTION | 3 |
| I. MISSING_CITATION_ONLY | 10 |
| K. EVALUATOR_LEXICAL_FALSE_NEGATIVE | 3 |
| A, B, D, E, F, G, H, J, L | 0 each |
| Null: no observed defect | 8 |

H is zero because the observed follow-up rewrite defect cannot be established
as the primary cause of its failed answer. It is retained as a separate finding
on the C row, not ignored or counted as another failed item.

| DEV item | Primary bucket | Manual observation |
| --- | --- | --- |
| qb2-001 | null | Correct 18 °C pre-screening storage temperature, cited on first pass |
| qb2-002 | null | Correct storage-temperature paraphrase, cited on first pass |
| qb2-003 | null | Correct preparation temperature; stable with the other two paraphrases |
| qb2-004 | I | Correct NBP-24C; citation and grammar repaired |
| qb2-005 | I | Correct 52 incoming cells, not 48 screened cells; citation repaired |
| qb2-006 | null | Correct abstention: no insurance coverage limit in rendered evidence |
| qb2-025 | K | Correct negative about face images; lexical mismatch; citation repaired |
| qb2-026 | C | Sampling hours fully rendered; abstained; rewrite also contains spurious “Describe” |
| qb2-027 | I | Correct 3,600 departures, not message count; citation repaired |
| qb2-028 | C | Both negative boundaries rendered; fully abstained |
| qb2-029 | I | Correct selected-release firmware MTS-2.4; citation repaired |
| qb2-030 | null | Correct abstention: timing intervals do not establish journey-time standard deviation |
| qb2-049 | I | Correct lead Sora Finn, not reviewer Ivo Marr; citation repaired |
| qb2-050 | I | Correct manual rain gauge reference, not handling blank; citation repaired |
| qb2-051 | I | Correct peak power 9 W, not daily heater energy; citation repaired |
| qb2-052 | K | Correct 31 paired rain-gauge comparisons; lexical mismatch; citation repaired |
| qb2-053 | I | Correct KFS-C7; citation and grammar repaired |
| qb2-054 | null | Correct abstention: site elevation does not give sensor height above ground |
| qb2-073 | null | Correct ARP-R9, cited on first pass |
| qb2-074 | C | Whole-family split method fully rendered; abstained |
| qb2-075 | I | Correct 240 manual files, not passages/families; citation repaired |
| qb2-076 | K | Correct negative about handwritten annotations; lexical mismatch; citation repaired |
| qb2-077 | I | Correct reviewer-comment retention 30 days, not 14-day snapshots; citation repaired |
| qb2-078 | null | Correct abstention: retrieval latency does not establish hardware power |

## False-abstention analysis

All three have `rendered_gold_all=true`, no citation repair, no missing gold
passage, and no contradictory answer to the requested property in the rendered
context. Relevant passages below are exact substrings of the saved rendered
blocks, not text recovered from full documents after the run.

**qb2-026 — follow-up, cause confounded.** Original question: “What hours does
it cover?” Retrieval and generation question: “What hours does it cover
regarding Describe and Meridian?” S1 (`meridian_protocol.md`) states:

> Meridian's sampling window is weekdays from 05:00 to 21:00.

It also states: “The window describes when the pilot measures activity, not when
the transit service itself operates.” Final output: “The provided documents do
not contain enough evidence to answer this.” The authored history establishes
the sampling plan, so the evidence directly answers the intended question.
Decision rules 2–3 should favor answering that fact. The service-hours qualifier
distinguishes scopes rather than making the sampling schedule unknown. However,
generation receives the awkward rewrite without the original history. Both a
resolver defect and a generation refusal are observed; this run cannot isolate
their causal contributions. There is no demonstrated gold/data error or genuine
ambiguity in the intended sampling-plan evidence.

**qb2-028 — unsupported refusal of two supported negative facts.** Original,
retrieval, and generation question: “Summarize Meridian’s boundaries for
face-image collection and inference of rider income.” S2 (`meridian_brief.md`):

> The Meridian study measures platform departures without collecting face images.

S1 (`meridian_incident.md`):

> Meridian's departure dataset cannot infer rider income.

The next sentence says no income variable or linked survey was collected. Final
output: “Insufficient evidence provided.” Both requested boundaries are explicit
and complementary. A supported answer would preserve both negatives with S2 and
S1 respectively. The prohibition on inferring income answers a question about
inference limits; it is not missing evidence about those limits. Current rules
2–5 should permit and require this answer. This is a generation/answerability
interpretation failure in observed behavior, potentially involving the negative
wording or two-part request; the internal cause is unproven. It is neither a
resolver change nor genuine evidence ambiguity, and no data issue is apparent.

**qb2-074 — refusal despite an explicit method.** Original, retrieval, and
generation question: “How does Atlas assign its manuals to development and
held-out partitions?” S1 (`atlas_methods.md`):

> Atlas assigns complete manual families to a split rather than splitting individual paragraphs at random.

The block defines a family as its overview, operating method, and revision
history. Its final caveat says the method does not guarantee independence from
every shared engineering term across families. Final output: “Insufficient
evidence provided.” The requested partitioning method is directly stated; no
split ratio or guarantee of perfect independence is requested. Rules 2–3 should
force an answer. The comparative wording and caveat may contribute to refusal,
but that is a prompt-interpretation hypothesis, not demonstrated causation.
There is no resolver change, relevant contradiction, or observed data issue.

## Wrong/incomplete answer analysis

Every raw `WRONG_ANSWER` has valid S1 support and full cited gold. Each was already
correct before its citation repair:

| Item | Fixed lexical label | Actual final answer | Manual interpretation |
| --- | --- | --- | --- |
| qb2-025 | `without collecting face images` | “The Meridian departure study does not collect passenger face images. [S1]” | Correct negative paraphrase of the rendered gold; no polarity reversal |
| qb2-052 | `31 paired comparisons` | “Kestrel accepted 31 paired rain-gauge comparisons after reference checks. [S1]” | Exact gold sentence with a marker; the intervening `rain-gauge` defeats substring matching |
| qb2-076 | `handwritten annotations are not evaluated` | “Atlas does not evaluate handwritten annotations in the manual margins. [S1]” | Exact gold sentence with a marker; active/passive wording differs from the label |

All three have lexical key-fact recall 0 and cited-gold recall 1.0. None selects a
wrong nearby entity/number, drops a required qualifier, overclaims, or chooses a
conflicting source. The JSON retains their exact rendered supporting sentences.
Manual review of the other 14 substantive answers likewise found no such error.

The sole multi-source item, qb2-028, leaves both labeled slots unmatched and
uncited because it abstains entirely. That is a real failure, but it does not
demonstrate a tendency to answer only one half of a two-part question. There is
too little DEV coverage to infer a general multi-source completeness rate.

## Missing-citation analysis

No final output ends `UNVERIFIED` or `missing_citations`. Looking only at final
status would hide 13 first-pass `missing_citations` results. Each saved answer
was **correct but had no marker**, including the three lexical false negatives.
There were zero partially correct, wrong, or unsupported first-pass answers in
these 13 cases, and no saved answer already contained a usable citation.

Only four of 17 substantive answers included valid citations without repair
(23.53% first-pass coverage): qb2-001, qb2-002, qb2-003, qb2-073. Repair was
necessary to satisfy the current citation validator for all other 13, despite
their content already being good. The seven abstentions do not require markers.

The raw report retains parsed first-pass text/status only when repair ran, not
the original first-pass raw JSON envelope. The saved strings and statuses show
marker omission; they do not support a separate diagnosis of a raw-envelope
parser/format defect. No new parser behavior is inferred.

## Citation-repair analysis

All 13 first-pass/final pairs were compared manually. Eleven are marker-only,
allowing movement of terminal punctuation. Two also correct grammar:

| Items | Manual classes | Substantive changes |
| --- | --- | ---: |
| qb2-005, qb2-025, qb2-027, qb2-029, qb2-049, qb2-050, qb2-051, qb2-052, qb2-075, qb2-076, qb2-077 | marker-only | 0 |
| qb2-004, qb2-053 | harmless formatting; paraphrase | 0 |

For qb2-004, “The project identifier belongs to the Northstar Battery Pilot is
NBP-24C.” becomes “The project identifier for the Northstar Battery Pilot is
NBP-24C [S1].” For qb2-053, “The calibration record key accompanies the Kestrel
method amendment is KFS-C7.” becomes “The calibration record key accompanying
the Kestrel method amendment is KFS-C7 [S1].” The same identifier/relation is
retained in each. The JSON provides verbatim first-pass and final text for every
repair, not just these two examples.

Manual counts: changed entity 0, number 0, polarity 0, added factual claim 0,
removed factual claim 0, improved factual correctness 0, worsened factual
correctness 0. Citation compliance improves in all 13. Repair classifications
may overlap; the two grammar repairs are both harmless formatting and paraphrase.

The raw drift heuristic also reports 11 `marker_only` and two `paraphrase`, but
those heuristic labels alone would not establish semantic safety. The manual
comparison supports zero substantive changes in this sample only. The current
`REPAIR_INSTRUCTIONS` contract, “using ONLY the same facts. Do not add claims,”
was respected in these observed answers. It receives the same context and no
new retrieval. There is no observed reason here to change repair safety logic.

## Follow-up analysis

There is one history item, qb2-026. Its authored history is:

- Question: “Describe the Meridian sampling plan.”
- Answer: “Meridian records platform departures during staffed collection windows.”
- Grounding status: `grounded`.

The new question is “What hours does it cover?” Resolver method `topic_expansion`
produces “What hours does it cover regarding Describe and Meridian?”, with
`rewrite_applied=true`. The same string is sent to generation; the generation
prompt does not receive the history separately.

The expected hints require Meridian and forbid Northstar, so the deterministic
`rewrite_error` flag is false. That token check misses the spurious topic
“Describe” and does not ensure the sampling-plan referent is explicit. This is
an observable resolver-quality defect. It did not prevent gold retrieval,
reranking, or rendering: the exact sampling-window sentence is S1. Generation
then abstained despite that sentence. A resolver fix might help, but the run
does not show that it would fix the refusal. No alternate rewrite was tested,
and no held-out follow-up was used for this diagnosis or recommendation.

## Conflict analysis

There are **zero DEV questions with expected conflict**. Some contexts contain
incidental disagreements or superseded values, but the DEV questions do not ask
the model to report both sides of those disputes. Thus zero collapsed conflicts
or false conflict reports is not evidence of successful conflict handling.
Both-side citation, averaging, invented authority, and conflict abstention cannot
be assessed usefully here. No test conflicts were inspected for tuning.

## Lexical-metric caveats

Three of six deterministic answer failures are correct paraphrases missed by
normalized substring matching. Keep the reported 0.70 key-fact recall unchanged
and report the manual judgments beside it. Do not rename that metric accuracy,
edit the labels to fit this model, or infer semantic correctness from citation-ID
validity or gold passage coverage. The three real false abstentions remain
failures even though their evidence was perfectly retrieved and rendered.

Evidence is bounded to at most 500 characters per quoted excerpt and 1000 per
example in the JSON, with exact offsets into the raw rendered block. All 123
blocks were reviewed; these excerpts are the audit pointers, not the complete
context. For unanswerable cases, a nearby excerpt illustrates a scope boundary;
absence of an answer was checked against all blocks, not inferred from that
one excerpt alone.

## Candidate hypotheses

The unchanged [generation prompt](../../src/research_assistant/generation/prompt.py)
already says to read every block, answer when the requested fact appears,
accept different phrasing, preserve grounded negatives, cite factual claims,
and report disagreements. It also forbids treating missing evidence as a
negative finding. The observed refusals violate the intended sufficiency rule;
the current instructions do not reliably elicit that behavior on this DEV run.
Correct negatives on qb2-025 and qb2-076 show the weakness is not universal.

| Candidate | DEV support and limitation | Decision |
| --- | --- | --- |
| A. Answerability/prompt clarification | Three supported refusals; two standalone questions rule out resolver changes for those cases. Negative, comparative, or qualified evidence may be misread as absence. | First experiment |
| B. Multi-part completeness prompt | One two-part item, fully refused; no observed partially completed substantive answer. Confounded with answerability. | Defer |
| C. Conflict handling prompt | No conflict questions. | Insufficient coverage |
| D. First-pass citation instruction improvement | 13 correct marker-free first passes; all recovered. Strong call-cost opportunity, but no remaining final-content defect from it. | Defer |
| E. Citation-repair safety change | Zero substantive changes in 13 repairs. | No observed drift to target |
| F. Follow-up resolver fix | One malformed rewrite, full gold still rendered; causal effect unknown. | Retain as separate hypothesis; defer |

## Recommended FIRST experiment

Recommend **exactly one: A, a prompt-only evidence-sufficiency clarification**.
It has not been implemented or run.

Hypothesis: explicitly distinguish a source-stated negative, limitation, or
qualified method that answers the requested property from a requested quantity
or property that the evidence does not provide. Preserve the statement's scope
and cite it. A general clarification of that distinction may reduce false
abstention without encouraging unsupported answers. Do not add DEV identifiers,
entity names, gold answers, or question-specific exceptions to the prompt.

The primary targets are qb2-028 and qb2-074. Monitor qb2-026 separately because
its resolver defect remains fixed and confounds interpretation. A future
authorized comparison should use the same 24 DEV items and report every item,
not select only the failures.

| Target metric | This run | Desired direction |
| --- | --- | --- |
| False abstentions with all gold rendered | 3 | Decrease |
| False abstention rate | 3/20 = 15% | Decrease |
| Manually correct answerable responses | 17/20 | Increase, preserving scope/qualifiers |
| qb2-028 supported parts answered and cited | 0/2 | Both parts, each supported by its own source |
| Cited-gold passage recall | 0.85 | Increase |
| Lexical key-fact recall | 0.70 | Report alongside manual review; do not use as semantic acceptance criterion |

Guardrails: retain four correct unanswerable abstentions (false-answer rate 0,
abstention recall 1.0); retain all 17 currently correct substantive answers;
keep final citation coverage 1.0 and malformed/invalid-citation counts zero;
introduce no unsupported claims or changed numbers, entities, or polarities;
keep substantive repair drift zero. Retrieval/rendered metrics must stay at
1.0. Report repair invocations and mean/p95 total latency against the observed
13 invocations and 9191.99/13041.08 ms, rather than concealing a cost increase.
The held-out TEST set remains sealed.

Keep benchmark bytes, labels, splits, corpus, embeddings, BM25/hybrid,
reranker, candidate depths, top-k, context budget, model/digest, temperature,
output limit, resolver, parser, JSON schema, citation and conflict rules,
repair code, repair-specific instructions, metric schema, and taxonomy fixed.
One subtlety: `build_repair_request` also includes `SYSTEM_INSTRUCTIONS`, so a
future change to that shared decision rule would also reach repairs even with
`REPAIR_INSTRUCTIONS` unchanged. Recheck all repaired pairs as a guardrail;
do not claim the entire repair request would be byte-identical.

This is a hypothesis from a single DEV observation, not a measured improvement
or a production recommendation. No conflict-quality improvement can be claimed
from this DEV split.

## What we explicitly should NOT change yet

- Do not rerun TEST, evaluate individual held-out IDs, regenerate the frozen
  baseline, or select prompts using held-out examples.
- Do not edit benchmark questions, labels, references, gold, corpus, or splits
  to improve lexical scores.
- Do not tune retrieval, reranking, chunking, or context budget: all gold was
  rendered on this run, including all three false abstentions.
- Do not combine a resolver, citation-formatting, multi-part, conflict, or
  repair-safety change with the first sufficiency experiment.
- Do not infer general semantic accuracy, conflict robustness, or universal
  repair safety from these 24 synthetic DEV cases.
- This diagnosis changes no production code, configuration, prompt, parser,
  resolver, repair behavior, or frozen baseline.

## Validation

| Check | Result |
| --- | --- |
| `python -m compileall -q src tests scripts evaluation` | Passed |
| `python -m pytest` in the existing workspace | 553 passed, 2 failed, 4 warnings; the two failures are untouched private tests expecting legacy selected-chunk semantics and the removed `all_slots_answered` field |
| `python -m pytest` in a clean public snapshot | 528 passed, 1 warning; snapshot contains the tracked source and these report changes, without private artifacts |
| `npm --prefix web test` | 188 passed across 16 files |
| `npm --prefix web run typecheck` | Passed |
| `npm --prefix web run lint` | Passed |
| `npm --prefix web run build` | Passed |
| `git diff --check` | Passed |
| Static diagnosis audit | All 24 DEV rows match raw fields; every excerpt and offset matches its rendered block; recomputed aggregate/slice metrics match |
| Protected bytes | Dataset, benchmark card, all 20 corpus documents, and both frozen baseline files unchanged |

The private failures do not make the full workspace run green; they are reported
separately from the passing public suite. Existing private files and serving
storage also retain their pre-task hashes. The Python suites include static
benchmark integrity checks; they did not execute the held-out live evaluation.
No production behavior or experiment was implemented during validation.
