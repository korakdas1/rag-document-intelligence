# qualitybench_v2 DEV first-pass citation-compliance experiment

**REJECT EXPERIMENT.** Both predeclared citation-improvement thresholds pass:
first-pass citations rise from 4/17 to 14/17 on the same previously substantive
cases, and citation repairs fall from 13/24 to 4/24. However, `qb2-028` replaces
an abstention with an unsupported, uncited answer. Final citation coverage falls
to 17/18 (94.44%). The no-unsupported-answer and final-citation guardrails fail.
Manually correct answerable items remain 17/20.

Exactly one v7 DEV run completed, with no technical restart. No second prompt
variant or rerun followed. The v7 candidate was rejected and reverted before
merge. Production remains on `grounded.answerability.v5`.

## Finalization

The experimental v7 implementation was evaluated once on DEV and rejected.
Before merge, the prompt, prompt tests, and generation README were restored
exactly to main commit `bbcb15939e4766c6f789e02c5a5cb9306f0a27b6`.
Production remains on `grounded.answerability.v5`. The final PR contains
experiment records only; merging it promotes no rejected behavioral change.
No live DEV rerun or held-out TEST evaluation was performed during finalization.

The experiment sections below, including configuration and validation, describe
the historical candidate at implementation commit
`b743523cefa4c754d9fc9bd665a10ecfbad6a957`, not the restored production state.
Historical metrics, run identities, hashes, and judgments are preserved.

## Identity and execution

| Identity | Value |
| --- | --- |
| Starting main | `bbcb15939e4766c6f789e02c5a5cb9306f0a27b6` |
| Starting main CI | [37198709348](https://github.com/korakdas1/rag-document-intelligence/actions/runs/37198709348), completed successfully |
| Branch | `experiment/first-pass-citation-compliance` |
| Implementation commit before live evaluation | `b743523cefa4c754d9fc9bd665a10ecfbad6a957` |
| Prompt comparison | `grounded.answerability.v5` → `grounded.answerability.v7` |
| v5 DEV run | `eval_20261004T092610Z_7e617cae80ec` |
| v5 raw SHA-256 | `befd206e7ff5b6d18f2e7672710a4f2f59b434ff5ca11482b778bf6e2bde2aa1` |
| v7 DEV run | `eval_20261004T114708Z_da306ea4f600` |
| v7 raw SHA-256 | `a31e0da80fd7f59dd02bc4bad3466643be21b933722cfa4f9197831543d3a8af` |
| Successful candidate runs / technical restarts | 1 / 0 |
| Execution UTC | 2026-10-04T11:46:54.528931+00:00 to 2026-10-04T11:50:42.256174+00:00; 227.727 seconds including preparation |
| Dataset SHA-256 | `4ae148bb8c375d667e1803e72ce977431e5b54cf250122ceeaa5d7fde3ddcc9f` |
| Corpus SHA-256 | `c9f92ea09c75cb2976201933c0f044be6b82a66491cc50b00d3783d2ea2f67cb` |
| Dataset / metric identities | `qualitybench_v2` / `qualitybench.v2` / `evidence-metrics.v2` |

The authoritative comparison is the committed [v5 DEV diagnosis](../diagnostics/qualitybench_v2_dev_generation_diagnosis_v1.md),
not a new baseline. Its metrics and manual judgments are preserved without
reinterpretation. The frozen TEST baseline and [rejected v6 record](qualitybench_v2_dev_sufficiency_v6.md)
are unchanged. v6 was not reused or rerun.

The [experiment JSON](qualitybench_v2_dev_citation_compliance_v7.json) includes
full aggregate comparisons, the fixed-population citation table, all 24 manual
judgments and exact final answers, all four repair pairs, every changed output,
configuration, and protected-file hashes.

The 445,939-byte raw report remains ignored locally at
`evaluation/results/qualitybench_v2_dev_citation_v7/eval_20261004T114708Z_da306ea4f600.json`.
It identifies the exact implementation commit above. The tracked tree was clean
before launch. The new isolated workspace is
`evaluation/workspaces/qualitybench_v2_dev_citation_v7/`; preparation indexed
141 chunks from 20 documents. Generation was uncached and repeat was 1.

The completed invocation was:

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 python -m research_assistant evaluate \
  --dataset evaluation/datasets/qualitybench_v2.jsonl \
  --corpus evaluation/corpus/quality_v2 \
  --workspace evaluation/workspaces/qualitybench_v2_dev_citation_v7 \
  --prepare --stage full --split dev --mode hybrid \
  --output evaluation/results/qualitybench_v2_dev_citation_v7
```

This command is a provenance record of the single completed run, not an
instruction to repeat it.

## Hypothesis and exact prompt change

A short final citation check near the JSON output instructions might make
first-pass citation requirements more salient without changing factual content
or answerability behavior. This was a formatting/compliance experiment. The
only behavioral change was the following block, inserted immediately before
“Return only a single JSON object,” plus the prompt identity change to v7:

> Final citation check before returning JSON:
> - If insufficient_evidence=false, verify that the answer string contains at least one valid [S#] marker from the supplied evidence.
> - If a substantive answer has no citation marker, add its supporting marker(s) before returning JSON. Do not change or invent facts merely to add citations.
> - Put each supporting marker next to the factual claim it supports. Use only citation IDs present in the evidence.
> - If insufficient_evidence=true, do not invent citation markers.

All previous system text is retained byte-for-byte after removing this added
block. Decision rules 1–6, evidence sufficiency wording, and the JSON protocol
are unchanged. No benchmark IDs, questions, answers, names, or case-specific
numbers were added. **10 focused prompt tests passed before the implementation
commit and live run.** They verify the v7 identity, unchanged answerability and
JSON rules, the final citation check, unchanged repair instructions, and shared
system guidance in repair requests; they do not simulate model success.

`REPAIR_INSTRUCTIONS`, `FORMAT_REPAIR_INSTRUCTIONS`, prompt functions, parser,
citation validator, service, and repair trigger remain unchanged.
`build_repair_request` includes `SYSTEM_INSTRUCTIONS`, so repairs also received
the new citation check. All four saved repair pairs were reviewed.

## Fixed environment and retrieval identity

All resolved settings and all 11 recorded dependency versions match the v5
DEV diagnosis. Python is 3.13.12; GPU is RTX 3050 Laptop with 4096 MiB and driver
595.91.07; local Ollama is 0.21.0. Only evaluation persistence paths moved.

| Component | Fixed value |
| --- | --- |
| Embedding | `BAAI/bge-small-en-v1.5`, revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, normalized, dimension 384, cosine, batch 32 |
| Chunker | `structure.v1:fc9ff956df32` |
| Retrieval | Dense/lexical candidates 20/20, BM25 1.2/0.75, RRF 60 |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2`, 20 candidates, top 8, batch 8, max length 512 |
| Context budget | 1024 |
| Generation | `qwen2.5-coder:7b`, temperature 0, max output 512, timeout 120 seconds |
| Qwen digest | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |
| Resolver / window / parser | `followup.heuristic.v4` / 4 / `json.object.v2` |
| Repair | Citation repair enabled, same model, at most one attempt; format repair disabled |

Runner configurations differ only in `prompt_id`. Model, chunker, index,
resolver, corpus, and dataset identities match. **All 24 resolved queries,
dense/lexical/hybrid/reranked ID lists, and all 123 exact rendered context blocks
match v5**, including order, citation IDs, provenance, and truncation. No
retrieval or environment mismatch was found. No hashing embeddings, overlap
reranker, scripted generation, or judge was used for the live run.

## Metrics and denominator policy

| Measure | v5 | v7 |
| --- | --- | --- |
| Substantive first-pass answers | 17 | 18 |
| First-pass valid citations, overall | 4/17 = 23.53% | 14/18 = 77.78% |
| First-pass valid citations, same v5 population | 4/17 = 23.53% | 14/17 = 82.35% |
| Substantive answers within that fixed population | 17/17 | 17/17 |
| Citation repair invocations | 13/24 | 4/24 |
| Total LLM calls | 37 | 28 |
| Mean LLM calls per item | 1.5417 | 1.1667 |
| Final citation coverage | 17/17 = 100% | 17/18 = 94.44% |
| Invalid citations / malformed outputs | 0 / 0 | 0 / 0 |
| Manually correct answerable items | 17/20 | 17/20 |
| Unsupported factual answers | 0 | 1 |
| False abstentions | 3/20 = 15% | 2/20 = 10% |
| Correct unanswerable abstentions | 4/4 | 4/4 |
| Unanswerable false-answer rate / abstention recall | 0% / 100% | 0% / 100% |
| Lexical key-fact recall / all facts matched | 70% / 70% | 70% / 70% |
| Cited-gold passage recall | 85% | 85% |
| GROUNDED / NOT_ENOUGH_EVIDENCE / UNVERIFIED | 17 / 7 / 0 | 17 / 6 / 1 |
| Gold hybrid / rerank / rendered all | 100% / 100% / 100% | 100% / 100% / 100% |
| Manual substantive repair changes | 0/13 | 0/4 |

The predeclared requirements were at least **8/17** first-pass citations on the
same v5 substantive-answer population and at most **9/24** repairs. Both pass.
All 17 original cases remain substantive; ten gain a first-pass citation and
none lose one. Three still need repair: `qb2-052`, `qb2-075`, and `qb2-076`.
`qb2-028` is a new substantive answer needing unsuccessful repair, making the
candidate's overall denominator 18. Thus overall coverage is **14/18**, while
the fixed-population comparison is **14/17**. Neither denominator is hidden.

First-pass coverage uses the saved parsed first-pass answer/status when repair
ran; otherwise the final output came from the sole generation call. A valid
first-pass citation requires a supplied inline ID and valid citation status.
The original first-pass raw JSON envelope is not retained when repair ran.
All final substantive outputs, including the unsupported one, count in final
citation coverage.

The false-abstention reduction is not a correctness gain: a refusal becomes an
unsupported answer. The deterministic taxonomy reports `WRONG_ANSWER` 3 → 4
and `FALSE_ABSTENTION_WITH_GOLD_CONTEXT` 3 → 2. The three established lexical
false negatives (`qb2-025`, `qb2-052`, `qb2-076`) remain semantically correct.
Their fixed lexical labels and historical judgments were not changed.

## Same 17 first-pass citation comparison

| Item | v5 first-pass valid marker | v7 first-pass valid marker | v5 repair | v7 repair | v7 manual correctness | v7 final citation |
| --- | --- | --- | --- | --- | --- | --- |
| qb2-001 | yes | yes | no | no | correct | valid (S1) |
| qb2-002 | yes | yes | no | no | correct | valid (S1) |
| qb2-003 | yes | yes | no | no | correct | valid (S1) |
| qb2-004 | no | yes | yes | no | correct | valid (S1) |
| qb2-005 | no | yes | yes | no | correct | valid (S1) |
| qb2-025 | no | yes | yes | no | correct paraphrase | valid (S1) |
| qb2-027 | no | yes | yes | no | correct | valid (S1) |
| qb2-029 | no | yes | yes | no | correct | valid (S1) |
| qb2-049 | no | yes | yes | no | correct | valid (S1) |
| qb2-050 | no | yes | yes | no | correct | valid (S1) |
| qb2-051 | no | yes | yes | no | correct | valid (S1) |
| qb2-052 | no | no | yes | yes | correct paraphrase | valid (S1) |
| qb2-053 | no | yes | yes | no | correct | valid (S1) |
| qb2-073 | yes | yes | no | no | correct | valid (S1) |
| qb2-075 | no | no | yes | yes | correct | valid (S1) |
| qb2-076 | no | no | yes | yes | correct paraphrase | valid (S1) |
| qb2-077 | no | yes | yes | no | correct | valid (S1) |

## Manual review of all 24 final answers

Review covered every final answer and all four saved first-pass/repair pairs
against the exact rendered evidence. All 123 blocks were reviewed, reading
identical repeated text once (78 distinct chunk/text pairs). This was not
independent human adjudication. The categories below total 24: 14 correct,
three correct paraphrases, two false abstentions, one unsupported answer, and
four correct abstentions. All 17 previously correct substantive answers remain
correct; there are no wrong-number, wrong-entity, or polarity regressions among
those 17.

| Item | v7 classification | Review |
| --- | --- | --- |
| qb2-001 | correct | Correct 18 degrees Celsius before screening; final answer and first-pass citation unchanged. |
| qb2-002 | correct | Correct 18 degrees Celsius preparation temperature; final answer and first-pass citation unchanged. |
| qb2-003 | correct | Correct pre-screening storage temperature; final answer and first-pass citation unchanged. |
| qb2-004 | correct | Correct NBP-24C identifier, now cited on the first pass. The awkward belongs to wording remains understandable; the identifier and project relation are unchanged. |
| qb2-005 | correct | Correct 52 incoming cells before exclusions, now cited on the first pass. Only terminal punctuation moves relative to S1. |
| qb2-006 | correct abstention | Correct abstention unchanged: engineering authorization and study scope do not provide an insurance coverage limit. |
| qb2-025 | correct paraphrase | Correct explicit negative: no passenger face images collected, now cited on the first pass. The fixed lexical label still misses this equivalent wording; final change is punctuation only. |
| qb2-026 | abstained | False abstention unchanged despite the complete weekday 05:00 to 21:00 sampling schedule. The same rewrite adds Describe as a topic and leaves the referent implicit; no causal resolver conclusion or intervention is made. |
| qb2-027 | correct | Correct 3,600 labeled departures during the initial staffed collection period, now cited on the first pass. No change to count, denominator, or qualification. |
| qb2-028 | unsupported | Unsupported answer replaces abstention. It misapplies the Stone Arch platform and maintenance-walkway departure-counting boundary to face-image collection, although S2 explicitly says no face images are collected. The later no-face-images/no-income-data clause is supported but does not cure that contradictory first sentence or explicitly state that income cannot be inferred. First pass and final answer are identical and uncited; repair fails to add markers or correct the existing error. |
| qb2-029 | correct | Correct MTS-2.4 firmware from the release notice, now cited on the first pass. Final answer is byte-identical to v5. |
| qb2-030 | correct abstention | Correct abstention unchanged: instrument latency and departure counts do not supply the standard deviation of complete passenger journey times. |
| qb2-049 | correct | Correct lead scientist Sora Finn, not field-log reviewer Ivo Marr; now cited on the first pass. Final change is punctuation only. |
| qb2-050 | correct | Correct manual rain gauge reference for the automatic precipitation channel, not a handling control; now cited on the first pass. |
| qb2-051 | correct | Correct 9 W peak panel rating, not integrated heater energy or battery capacity; now cited on the first pass. |
| qb2-052 | correct paraphrase | Correct 31 paired rain-gauge comparisons after reference checks. The intervening rain-gauge wording still defeats the fixed substring label. Repair adds only S1; final answer is unchanged. |
| qb2-053 | correct | Correct KFS-C7 calibration record key, now cited on the first pass. The awkward accompanies wording preserves the same key and relation; no factual regression. |
| qb2-054 | correct abstention | Correct abstention unchanged: site elevation is not sensor mounting height above ground, which is absent from all rendered blocks. |
| qb2-073 | correct | Correct ARP-R9 identifier; final answer and first-pass citation unchanged. |
| qb2-074 | abstained | False abstention unchanged despite S1 explicitly assigning complete manual families, not random paragraphs. The nearby limitation does not remove that method statement. |
| qb2-075 | correct | Correct 240 manual files, not passages or families. Repair adds only S1; final answer is unchanged. |
| qb2-076 | correct paraphrase | Correct negative about handwritten notes/annotations in manual margins. Repair removes redundant No, uses the equivalent annotations wording, and adds S1; it does not reverse polarity or change an entity. Final answer is unchanged; the fixed lexical label still misses the active formulation. |
| qb2-077 | correct | Correct 30-day reviewer-comment retention after review closes, not the 14-day rollback schedule; now cited on the first pass. |
| qb2-078 | correct abstention | Correct abstention unchanged: the evidence explicitly says hardware power was not measured; retrieval/delivery timing cannot supply it. |

## Unsupported answer and answerability change

For `qb2-028`, S2 explicitly states:

> The Meridian study measures platform departures without collecting face images.

S1 states:

> Meridian's departure dataset cannot infer rider income. No income variable or linked survey was collected.

S2 separately describes the Stone Arch platform and a maintenance walkway
outside the **departure-counting** boundary. These location details do not
define a face-image collection region. v5 abstained. v7 returns the same answer
before and after repair:

> Meridian's boundaries for face-image collection include the Stone Arch platform on corridor C, excluding a maintenance walkway beside the platform. For inference of rider income, Meridian does not collect face images or income data.

The first sentence incorrectly transfers the counting boundary to face-image
collection. The later no-collection clause is supported but contradicts that
first sentence's framing and does not explicitly state the income-inference
limit. No rendered block supports the claimed image-collection region. This
is a substantive unsupported answer, not just lexical mismatch or a missing
marker. It has no citations before or after repair.

The other two false abstentions, `qb2-026` and `qb2-074`, remain unchanged.
The malformed follow-up rewrite for `qb2-026` also remains identical; its causal
contribution was not tested. All four unanswerable items (`qb2-006`, `qb2-030`,
`qb2-054`, `qb2-078`) retain their exact correct abstentions.

## Every final-output change

Ten final strings change; fourteen are byte-identical. Seven changes concern
terminal punctuation relative to S1, two preserve facts with awkward grammar,
and one replaces an abstention with an unsupported answer. The JSON records
both full answers and statuses for every changed item.

| Item | v5 → v7 status | Change classification | Factual meaning changed |
| --- | --- | --- | --- |
| qb2-004 | GROUNDED → GROUNDED | awkward grammar; factual meaning unchanged | no |
| qb2-005 | GROUNDED → GROUNDED | terminal punctuation relative to citation only | no |
| qb2-025 | GROUNDED → GROUNDED | terminal punctuation relative to citation only | no |
| qb2-027 | GROUNDED → GROUNDED | terminal punctuation relative to citation only | no |
| qb2-028 | NOT_ENOUGH_EVIDENCE → UNVERIFIED | unsupported substantive answer replaces abstention | yes |
| qb2-049 | GROUNDED → GROUNDED | terminal punctuation relative to citation only | no |
| qb2-050 | GROUNDED → GROUNDED | terminal punctuation relative to citation only | no |
| qb2-051 | GROUNDED → GROUNDED | terminal punctuation relative to citation only | no |
| qb2-053 | GROUNDED → GROUNDED | awkward grammar; factual meaning unchanged | no |
| qb2-077 | GROUNDED → GROUNDED | terminal punctuation relative to citation only | no |

For `qb2-004`, “identifier for” becomes “identifier belongs to”; for `qb2-053`,
“key accompanying” becomes “key accompanies.” The identifiers and relations
remain correct, although phrasing is less polished. These are not hidden as
byte-identical outputs or misclassified as factual regressions.

## Citation repair audit

| Item | First pass | Final answer | Manual classification |
| --- | --- | --- | --- |
| qb2-028 | Meridian's boundaries for face-image collection include the Stone Arch platform on corridor C, excluding a maintenance walkway beside the platform. For inference of rider income, Meridian does not collect face images or income data. | Meridian's boundaries for face-image collection include the Stone Arch platform on corridor C, excluding a maintenance walkway beside the platform. For inference of rider income, Meridian does not collect face images or income data. | unchanged; citation repair unsuccessful |
| qb2-052 | Kestrel accepted 31 paired rain-gauge comparisons after reference checks. | Kestrel accepted 31 paired rain-gauge comparisons after reference checks. [S1] | marker-only |
| qb2-075 | Atlas's frozen source inventory contains 240 manual files. | Atlas's frozen source inventory contains 240 manual files. [S1] | marker-only |
| qb2-076 | No, Atlas does not evaluate handwritten notes in manual margins. | Atlas does not evaluate handwritten annotations in the manual margins. [S1] | paraphrase, harmless formatting |

Two repairs add only S1. The `qb2-076` repair removes the redundant leading “No,” and
changes “notes” to the synonymous “annotations,” and adds S1. Both versions
retain **does not evaluate** and the same handwritten-margin subject. The raw
heuristic reports `polarity_change` and `entity_change`; manual review finds
both flags to be false positives. The raw flags remain recorded separately in JSON. No number,
entity, polarity, or factual claim changes in any repair: manual substantive
drift is **0/4**, compared with 0/13 for v5.

The fourth repair (`qb2-028`) repeats its unsupported answer exactly. Zero
repair drift does not mean correctness or successful citation repair: three
repairs restore citations and one fails. The new factual error originates in
the first pass, not in repair.

## Latency and calls

| Stage | v5 mean / p95, ms | v7 mean / p95, ms | Mean / p95 change |
| --- | --- | --- | --- |
| First-pass generation | 5677.34 / 6575.56 | 7325.24 / 9898.86 | +29.03% / +50.54% |
| Repair, including zero for unrepaired rows | 3447.59 / 6890.05 | 1377.64 / 7576.49 | -60.04% / +9.96% |
| Total generation | 9124.94 / 12962.86 | 8702.88 / 14301.10 | -4.63% / +10.32% |
| Total row | 9191.99 / 13041.08 | 8776.04 / 14377.93 | -4.53% / +10.25% |

Calls fall from **37 to 28**, or **1.5417 to 1.1667 per item**. First-pass mean
latency rises 29.03%, while repair time falls with nine fewer repair calls.
Total mean latency falls **4.53%**, and total p95 rises **10.25%**. Neither total
measure regresses by 20% or more. These are all-row metrics, including zero
repair time for unrepaired rows; the unchanged metric schema also retains cold
and warm diagnostics in JSON.

Timing is secondary. One historical run and one candidate run are not a
replicated, randomized, or interleaved performance benchmark. No full test
suite or frontend build ran concurrently with the live experiment. The observed
mean reduction is modest despite fewer calls, and cannot establish a stable
latency benefit. Rejection rests on factual and citation failures, not timing.

## Predeclared thresholds, guardrails, and decision

| Requirement | Result | Evidence |
| --- | --- | --- |
| At least 8/17 first-pass-cited answers on the same v5 substantive population | PASS | 14/17 |
| At most 9/24 citation repair invocations | PASS | 4/24 |
| All 17 previously correct substantive answers remain manually correct | PASS | 17/17 preserved; two awkward grammar changes do not change facts. |
| No new unsupported factual answer, wrong number/entity, polarity reversal, or unjustified extrapolation | **FAIL** | qb2-028 misapplies the platform/walkway counting boundary to face-image collection. The later no-collection clause does not cure the first claim. |
| All four unanswerable items abstain; false-answer rate 0%; abstention recall 100% | PASS | qb2-006, qb2-030, qb2-054, qb2-078 all remain correct abstentions. |
| No more than three false abstentions | PASS | Two remain: qb2-026 and qb2-074. The removed abstention becomes unsupported, not an answer-quality gain. |
| 100% final substantive-answer citation coverage | **FAIL** | 17/18 (94.44%); qb2-028 is uncited before and after repair. |
| Zero invalid citations | PASS | 0 |
| Zero malformed outputs | PASS | 0 |
| Zero manual substantive repair changes | PASS | 0/4. qb2-076 has harmless paraphrase despite raw heuristic flags; qb2-028 repeats an existing error. |
| Gold hybrid/rerank/rendered all 100%; queries, candidate IDs, and rendered evidence identical | PASS | All three rates are 1.0. All 24 query/candidate lists and all 123 rendered blocks match v5, including citation IDs, provenance, order, and truncation. |

**REJECT EXPERIMENT.** Passing the citation and repair thresholds is insufficient
when a new unsupported factual answer appears and final citation coverage
falls below 100%. The evaluated candidate was not tuned or rerun after completion;
no second variant followed. Finalization restored v5 instead of promoting the
rejected candidate.

## Limitations and held-out TEST policy

This is one controlled 24-item DEV run, not a general-accuracy estimate. DEV has
no conflict questions, one multi-source question, and one follow-up with an
unchanged resolver anomaly. Manual correctness remains separate from lexical
key-fact matching and citation-ID validity. The system-guidance change also
reaches citation repair, so this is not an isolated change to first-pass requests
alone, even though repair-specific instructions and service logic are unchanged.

**Held-out TEST was not run.** No individual held-out TEST IDs were evaluated,
no TEST outputs informed prompt wording, and the frozen TEST baseline was not
regenerated. The benchmark, corpus, labels, references, splits, v5 DEV diagnosis,
and rejected v6 experiment record remain byte-identical. No other experiment
was started. Ordinary offline unit/integration tests are separate from held-out
live evaluation.

## Experiment validation (historical)

| Check | Result |
| --- | --- |
| Focused prompt tests before implementation commit and live run | 10 passed |
| `python -m compileall -q src tests scripts evaluation` | Passed |
| `python -m pytest` in the existing workspace | 554 passed, 5 failed, 4 warnings |
| `python -m pytest` in the public snapshot | 532 passed, 1 deprecation warning |
| `npm --prefix web test` | 188 passed across 16 files |
| `npm --prefix web run typecheck` | Passed |
| `npm --prefix web run lint` | Passed |
| `npm --prefix web run build` | Passed |
| `git diff --check`, including staged records | Passed |
| Static record audit | Raw identities, historical values, all published examples/excerpts, same-17 counts, changed outputs, repair pairs, and guardrails verified; saved DEV metrics and slices recomputed exactly |
| Protected-file hashes | All 28 benchmark/card/corpus/baseline/diagnosis/v6-record files unchanged |

The full workspace suite was **not green**. Its five failures were in unchanged
private/untracked tests: two legacy evidence/slot-metric assertions already
failed before this experiment, and three hard-code v5 and were incompatible
with the candidate's v7 identity. These files were not edited to suppress failures.
The public snapshot included all tracked files plus the new experiment records
and README link, excluding pre-existing private artifacts. Subsequent edits
only clarified report wording and appended validation results.

All 70 original private files and 81 serving-storage files retained their original
hashes. At experiment validation time, the candidate prompt matched the pre-run
implementation commit.
No live evaluation was repeated during validation.
