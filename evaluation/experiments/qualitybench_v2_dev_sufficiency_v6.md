# qualitybench_v2 DEV evidence-sufficiency experiment

**REJECT EXPERIMENT.** The one completed v6 run reduces false abstentions from
three to two by replacing a refusal with an unsupported, uncited answer. It
does not increase the manually correct answerable count: that remains 17/20.
Required guardrails B (no unsupported factual answer) and D (100% final citation
coverage) fail. No second prompt variant or additional live run was attempted.
The candidate is retained on an unmerged experiment branch for review.

## Identity and execution

| Identity | Value |
| --- | --- |
| Starting main | `e0d903b28404743f9de2cf5be193de0711f8c1ad` |
| Starting main CI | [37195488802](https://github.com/korakdas1/rag-document-intelligence/actions/runs/37195488802), completed successfully |
| Branch | `experiment/evidence-sufficiency-prompt` |
| Implementation commit, made before live evaluation | `666e18b1368ecc5bd92448a28fd8b7b4975bef27` |
| Prompt comparison | `grounded.answerability.v5` → `grounded.answerability.v6` |
| v5 DEV run | `eval_20261004T092610Z_7e617cae80ec` |
| v5 raw SHA-256 | `befd206e7ff5b6d18f2e7672710a4f2f59b434ff5ca11482b778bf6e2bde2aa1` |
| v6 DEV run | `eval_20261004T104152Z_2ed8ce8d203b` |
| v6 raw SHA-256 | `7b9127d40ab6ca4ac52901b52cb176bb776348bc54dd70a027f2bedd5a949fd2` |
| Successful completed candidate runs / technical restarts | 1 / 0 |
| v6 execution UTC | 2026-10-04 10:41:43–10:46:47; 304.236 seconds including preparation |
| Dataset SHA-256 | `4ae148bb8c375d667e1803e72ce977431e5b54cf250122ceeaa5d7fde3ddcc9f` |
| Corpus SHA-256 | `c9f92ea09c75cb2976201933c0f044be6b82a66491cc50b00d3783d2ea2f67cb` |
| Dataset / metric identities | `qualitybench_v2` / `qualitybench.v2` / `evidence-metrics.v2` |

The baseline is the committed [DEV diagnosis](../diagnostics/qualitybench_v2_dev_generation_diagnosis_v1.md),
not the frozen TEST baseline. Historical metrics and manual judgments are copied
without reinterpretation. The [experiment JSON](qualitybench_v2_dev_sufficiency_v6.json)
contains full aggregate comparisons, all 24 per-example judgments, four changed
final outputs, all 16 repair pairs, configuration, and protected-file hashes.

The 448,039-byte raw v6 report remains ignored locally at
`evaluation/results/qualitybench_v2_dev_sufficiency_v6/eval_20261004T104152Z_2ed8ce8d203b.json`.
It identifies the exact implementation commit above. The fresh isolated workspace
is `evaluation/workspaces/qualitybench_v2_dev_sufficiency_v6/`. The tracked tree
was clean before launch. Preparation indexed 141 chunks from 20 documents.

The recorded invocation used the same Python environment as the diagnosis:

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 python -m research_assistant evaluate \
  --dataset evaluation/datasets/qualitybench_v2.jsonl \
  --corpus evaluation/corpus/quality_v2 \
  --workspace evaluation/workspaces/qualitybench_v2_dev_sufficiency_v6 \
  --prepare --stage full --split dev --mode hybrid \
  --output evaluation/results/qualitybench_v2_dev_sufficiency_v6
```

This command has already completed once; it is a provenance record, not a request
to repeat the experiment.

## Hypothesis and single change

The preselected hypothesis was that an explicit negative, limitation, exclusion,
qualification, or method might be mistaken for absence of evidence. The sole
behavioral variable was four lines added to the grounded decision guidance,
with the prompt identity advanced to v6. The exact added guidance is:

> Before setting insufficient_evidence=true, check every evidence block for a statement that directly answers the requested property.
> A source-stated negative, limitation, or exclusion is evidence when it directly answers what is or is not included, possible, or supported. Words such as "not", "cannot", "does not", or "excludes" do not mean evidence is absent.
> An explicit method or procedure answers how something is done; a nearby caveat about what it does not guarantee does not erase that direct answer. Preserve the negative or qualification when answering.
> If the source says nothing about the requested property or value, or discusses only a related thing without the requested method or property, the evidence is still insufficient.

All existing system text remains present, including the rule that missing
evidence is not itself a negative finding. No benchmark names, IDs, answers,
or copied benchmark sentences were added to the prompt. Focused prompt tests
passed **10/10 before the implementation commit and live run**. They cover the
general sufficiency contract, v6 identity, citations, JSON types, and shared
guidance in repair requests; they do not simulate model success.

`REPAIR_INSTRUCTIONS`, repair request construction, citation validation,
parser, and JSON protocol are unchanged. Because repair requests also include
`SYSTEM_INSTRUCTIONS`, repairs see the same new v6 sufficiency guidance. All
repair pairs were therefore included in the review.

## Fixed dimensions and environment

Resolved settings equal both the diagnosis settings and cleared-environment
defaults. Only persistence paths move into the isolated workspace. Python
3.13.12 and the recorded dependency versions match the diagnosis environment.
GPU: RTX 3050 Laptop, 4096 MiB, driver 595.91.07; local Ollama 0.21.0.

| Component | Fixed setting |
| --- | --- |
| Embedding | `BAAI/bge-small-en-v1.5`, normalized, dimension 384, cosine, batch 32 |
| Embedding identity | `bge-small-en-v1.5:73115d06b057`; revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` |
| Chunker | `structure.v1:fc9ff956df32` |
| Retrieval | BGE/BM25 hybrid; dense/lexical candidates 20/20; BM25 1.2/0.75; RRF 60 |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2`; identity `ms-marco-MiniLM-L-6-v2:603b5a7fd2cf`; 20 candidates, top 8, batch 8, max length 512 |
| Context budget | 1024 |
| LLM | `qwen2.5-coder:7b`; identity `qwen2.5-coder-7b:8f6776b6b431`; temperature 0, max output 512, timeout 120 seconds |
| Qwen digest | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |
| Resolver / parser | `followup.heuristic.v4` / `json.object.v2` |
| Repair | Citation repair enabled, same model, at most one attempt; format repair disabled |

Runner configurations differ only in `prompt_id`. Model, chunker, index and
resolver identities, corpus/dataset hashes, and all 24 resolved questions match.
Hybrid/rerank candidate ID lists and **all 123 complete rendered context blocks
are identical**, including order, citation IDs, provenance, and truncation flags.
No environmental or retrieval mismatch explains the changed answer.

## DEV comparison

All values concern the fixed 24 DEV examples: 20 answerable and four unanswerable.
No hashing embeddings, overlap reranker, scripted generation, or judge was used
for either live run.

| Measure | v5 | v6 |
| --- | ---: | ---: |
| GROUNDED | 17 | 17 |
| NOT_ENOUGH_EVIDENCE | 7 | 6 |
| UNVERIFIED | 0 | 1 |
| False abstentions with all gold rendered | 3 | 2 |
| False-abstention rate | 15% | 10% |
| False-answer rate on unanswerable items | 0/4 = 0% | 0/4 = 0% |
| Abstention recall | 100% | 100% |
| Abstention precision | 4/7 = 57.14% | 4/6 = 66.67% |
| Manually correct answerable items | 17/20 | 17/20 |
| Manually unsupported factual answers | 0 | 1 |
| Lexical key-fact recall / all facts matched | 70% / 70% | 70% / 70% |
| Cited-gold passage recall | 85% | 85% |
| Final citation coverage | 17/17 = 100% | 17/18 = 94.44% |
| Final missing citations | 0 | 1 |
| Invalid citations / malformed outputs | 0 / 0 | 0 / 0 |
| Gold in hybrid / rerank / rendered all | 100% each | 100% each |
| Multi-source labeled slots matched / cited | 0/2 / 0/2 | 0/2 / 0/2 |

The unchanged deterministic taxonomy reports `WRONG_ANSWER` 3 → 4 and
`FALSE_ABSTENTION_WITH_GOLD_CONTEXT` 3 → 2. The three existing wrong-answer labels
remain lexical false negatives (`qb2-025`, `qb2-052`, `qb2-076`). The fourth,
`qb2-028`, is a real unsupported answer, with `MISSING_CITATION` secondary failure.
The unanswerable false-answer rate staying zero does not excuse an unsupported
answer on an answerable question; these are different populations.

## Target outcomes

**qb2-028 fails.** The question asks for the face-image collection and income
inference boundaries. In the unchanged rendered context, S2 says:

> The Meridian study measures platform departures without collecting face images.

S1 says:

> Meridian's departure dataset cannot infer rider income.

It immediately adds that no income variable or linked survey was collected.
Separately, S2 describes a maintenance walkway outside the departure-counting
boundary so equipment crews are not counted as passengers. That spatial boundary
does not define a face-image collection region.

v5 abstained. v6's first pass and final answer are identical:

> Meridian's boundaries for face-image collection do not include the platform exit line, as staff mark that boundary to exclude equipment crews from being counted as passengers. The inference of rider income is not possible with the collected data, as no income variable or linked survey was collected.

The first sentence wrongly transfers the departure-counting boundary to
face-image collection and invents the exit-line exclusion. It also fails to
state the actual no-collection boundary. The second sentence correctly
paraphrases the income limitation. Thus one of two requested parts is manually
correct, but the whole answer is **unsupported**, not merely a lexical mismatch
or an incomplete otherwise-correct response. It has no citations before or after
repair. No additional rendered block supports the invented face-image boundary.

**qb2-074 remains a false abstention.** S1 still explicitly describes assigning
complete manual families instead of random paragraphs, followed by the definition
of a family and a caveat about shared terms. Both versions return “Insufficient
evidence provided.” The method sufficiency clarification did not rescue this
target.

**qb2-026 remains a monitor-only false abstention.** Both versions receive the
same rewrite, “What hours does it cover regarding Describe and Meridian?”, and
the same explicit sampling schedule in S1. Both abstain. The spurious topic and
implicit referent remain unchanged; no resolver fix or alternate rewrite was
attempted.

## Manual review of all 24 items

Review was output-by-output against exact rendered evidence, including every
saved first-pass/repair pair. This was not independent human adjudication.
Complete rendered contexts were verified identical to the reviewed v5 contexts;
the new unsupported answer received an additional full-context inspection.

Historical v5 judgments remain as committed. The v6 categories below total 24:
14 correct, three correct paraphrases, two abstained on answerable items, one
unsupported, and four correct abstentions. No previously correct substantive
answer becomes incomplete, wrong, or unsupported.

| Item | v6 manual classification | Observation |
| --- | --- | --- |
| qb2-001 | correct | Same 18 °C preparation temperature; now needs citation repair |
| qb2-002 | correct | Same storage temperature, cited on first pass |
| qb2-003 | correct | Same preparation temperature, cited on first pass |
| qb2-004 | correct | Same NBP-24C; harmless grammar/citation repair |
| qb2-005 | correct | Same 52 incoming cells, preserving exclusions |
| qb2-006 | correct abstention | Insurance coverage limit absent; unchanged |
| qb2-025 | correct paraphrase | Same supported negative; lexical false negative persists |
| qb2-026 | abstained | Same false abstention and malformed rewrite; monitor only |
| qb2-027 | correct | Same 3,600 staffed-period departures |
| qb2-028 | unsupported | Invented face-image boundary, correct income limit, no citations |
| qb2-029 | correct | Same release-notice firmware MTS-2.4 |
| qb2-030 | correct abstention | Complete journey-time standard deviation absent; unchanged |
| qb2-049 | correct | Same lead Sora Finn |
| qb2-050 | correct | Same manual rain gauge reference |
| qb2-051 | correct | Same 9 W peak panel rating |
| qb2-052 | correct paraphrase | Same supported count/object; lexical label misses intervening words |
| qb2-053 | correct | Same KFS-C7; harmless grammar/citation repair and punctuation change |
| qb2-054 | correct abstention | Sensor height above ground absent; elevation is different |
| qb2-073 | correct | Same ARP-R9; now needs citation repair |
| qb2-074 | abstained | Same false abstention despite explicit method |
| qb2-075 | correct | Same 240 manual files |
| qb2-076 | correct paraphrase | Same negative; active/passive lexical mismatch persists |
| qb2-077 | correct | Same 30-day reviewer-comment retention |
| qb2-078 | correct abstention | Hardware power unmeasured; unchanged |

## Changed-output comparison

Only four final strings differ; the other 20 are byte-identical. To avoid hiding
changes, this table includes even punctuation-only differences. All final texts,
historical/manual judgments, citation states, and key-fact scores are preserved
side by side in JSON.

| Item | v5 → v6 status | v5 → v6 manual judgment | Key-fact recall | Final citation state | Explanation |
| --- | --- | --- | --- | --- | --- |
| qb2-001 | GROUNDED → GROUNDED | correct → correct | 1 → 1 | S1 → S1 | Period moves before marker; first pass loses its marker, now repaired |
| qb2-028 | NOT_ENOUGH_EVIDENCE → UNVERIFIED | false abstention → unsupported | 0 → 0 | No marker, abstention → no marker, substantive answer | Invented face-image boundary; repair leaves output unchanged |
| qb2-053 | GROUNDED → GROUNDED | correct → correct | 1 → 1 | S1 → S1 | Period moves before marker; meaning unchanged |
| qb2-073 | GROUNDED → GROUNDED | correct → correct | 1 → 1 | S1 → S1 | Period moves before marker; first pass loses its marker, now repaired |

## Citation repair and first-pass behavior

First-pass citation coverage falls from **4/17 (23.53%) to 2/18 (11.11%)** of
substantive answers. Only qb2-002 and qb2-003 cite on the first pass in v6.
Repair invocations rise from 13 to 16; new repairs are qb2-001, qb2-028, qb2-073.
Of the 16 first passes needing repair, 15 are otherwise correct and one is
already unsupported. Fifteen repairs restore citation compliance; one fails.

| v6 repair class | Count | Items |
| --- | ---: | --- |
| Marker-only, allowing terminal punctuation movement | 13 | qb2-001, qb2-005, qb2-025, qb2-027, qb2-029, qb2-049, qb2-050, qb2-051, qb2-052, qb2-073, qb2-075, qb2-076, qb2-077 |
| Harmless formatting / paraphrase | 2 | qb2-004, qb2-053 |
| Unchanged, unsuccessful citation repair | 1 | qb2-028 |

Manual substantive drift is **0/16**, compared with 0/13 in v5: no entity,
number, polarity, or factual claim was added, removed, or changed by repair.
The two grammar repairs retain the same identifier relations. In qb2-028, the
entire erroneous first-pass answer is repeated exactly. Zero repair drift is
therefore not proof of answer correctness or successful repair. The wrong claim
originates in the first pass, not in the repair.

The raw heuristic lists 13 `marker_only` and two `paraphrase` changes; the
unchanged sixteenth repair contributes no drift kind. All 16 pairs, their
parsed first-pass statuses, final statuses, and manual comparisons appear in
the JSON. Original first-pass raw JSON envelopes are not retained by the
existing report format, a limitation unchanged from v5.

## Latency and calls

| Measure | v5 | v6 |
| --- | ---: | ---: |
| Total LLM calls | 37 | 40 |
| Mean calls per item | 1.5417 | 1.6667 |
| Repair invocations | 13/24 | 16/24 |
| First-pass latency mean / p95, ms | 5677.34 / 6575.56 | 6855.47 / 8839.36 |
| Repair latency mean / p95, ms, including zero for unrepaired rows | 3447.59 / 6890.05 | 5194.77 / 11648.49 |
| Total generation mean / p95, ms | 9124.94 / 12962.86 | 12050.24 / 19245.12 |
| Total row mean / median / p95, ms | 9191.99 / 11150.92 / 13041.08 | 12122.44 / 12976.40 / 19339.84 |

Mean total latency rises **31.88%** and p95 **48.30%**, with three additional
LLM calls. This is a material observed cost increase, not dismissed as tiny
noise. The two single runs were not randomized/interleaved hardware benchmarks;
the comparison cannot isolate all timing variation from longer prompts,
different outputs, extra repairs, or system conditions. No full test suite or
frontend build ran concurrently with the live candidate evaluation. Rejection
rests on factual and citation failures, independently of timing.

## Acceptance guardrails and decision

| Guardrail | Result | Evidence |
| --- | --- | --- |
| A. Four correct unanswerable abstentions | PASS | All four unchanged; false-answer rate 0%, abstention recall 100% |
| B. No unsupported factual answer | **FAIL** | qb2-028 introduces an unsupported face-image collection boundary |
| C. Preserve 17 correct substantive answers | PASS | All 17 remain correct |
| D. Final citation coverage 100% | **FAIL** | 17/18; qb2-028 lacks markers after repair |
| E. Invalid citations 0 | PASS | 0 |
| F. Malformed outputs 0 | PASS | 0 |
| G. Retrieval/rerank/rendered gold 100% | PASS | All rates 1.0; exact retrieval/context equality also verified |
| H. Substantive repair drift 0 | PASS | 0/16; one unchanged erroneous answer is not counted as new repair drift |

**REJECT EXPERIMENT.** Neither primary target becomes correctly answered with
citations. The apparent improvement in refusal count is an unsafe answerability
transition, with no increase in correct answerable responses. Citation coverage
also falls below the required threshold. The candidate prompt was not edited
after the completed run; no rescue change, second variant, or rerun followed.

## Limitations and held-out test policy

This is one candidate DEV run compared with the committed historical DEV run,
not an estimate of general accuracy. Lexical matching remains separate from
manual correctness. DEV has zero conflict questions, one multi-source question,
and one follow-up with a known rewrite limitation. The comparison cannot
establish broad conflict, repair, or follow-up robustness.

**Held-out TEST was not run.** No individual held-out IDs were evaluated, no
test outputs guided wording, and the frozen TEST baseline was not regenerated.
Benchmark, corpus, gold, key facts, references, and historical diagnosis/baseline
bytes remain unchanged. Ordinary offline unit/integration tests are separate
from held-out live evaluation. No other prompt experiment was started.

## Validation

| Check | Result |
| --- | --- |
| Focused prompt tests before live evaluation | 10 passed |
| `python -m compileall -q src tests scripts evaluation` | Passed |
| `python -m pytest` in the existing workspace | 554 passed, 5 failed, 4 warnings |
| `python -m pytest` in the public snapshot | 532 passed, 1 deprecation warning |
| `npm --prefix web test` | 188 passed across 16 files |
| `npm --prefix web run typecheck` | Passed |
| `npm --prefix web run lint` | Passed |
| `npm --prefix web run build` | Passed |
| `git diff --check` | Passed |
| Static experiment audit | All raw fields, historical judgments, changed outputs, repair pairs, and excerpt offsets verified; DEV aggregates and slice reports recomputed exactly |
| Protected-file hashes | All 26 benchmark/card/corpus/baseline/diagnosis files unchanged |

The full workspace run is **not green**. Its five failures are in untouched
private/untracked tests: two expect legacy evidence/slot metrics and already
failed before this experiment; three hard-code v5 and now fail because of the
required v6 version bump. Those files were not edited to suppress the failures.
The public snapshot includes the implementation and report files while excluding
private artifacts. Subsequent report edits only append these validation results.
The 70 existing private files and 81 serving-storage files retain their pre-task
hashes. The candidate prompt still matches the pre-run implementation commit.
