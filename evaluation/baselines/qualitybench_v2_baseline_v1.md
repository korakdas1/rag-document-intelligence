# qualitybench_v2 frozen baseline

## Identity

| Field | Value |
| --- | --- |
| Baseline | `qualitybench_v2_baseline_v1` |
| Source commit | `98db5679f5b6b9477a23079fdf6fc9524e1adb40` |
| Source CI | [CI 37180872656](https://github.com/korakdas1/rag-document-intelligence/actions/runs/37180872656) — success (post-merge push) |
| Run timestamp (UTC) | 20261004T060418Z |
| Metrics schema | evidence-metrics.v2 |
| Dataset | qualitybench_v2 / qualitybench.v2 |
| Dataset SHA-256 | `4ae148bb8c375d667e1803e72ce977431e5b54cf250122ceeaa5d7fde3ddcc9f` |
| Corpus SHA-256 | `c9f92ea09c75cb2976201933c0f044be6b82a66491cc50b00d3783d2ea2f67cb` |
| Raw run ID | `eval_20261004T060418Z_877bd388bf34` |
| Raw report SHA-256 | `b182bf3d0203cbb7d0f0cf1a09269e2e0420c41032cb7dc9acfe6c488859d870` |
| Ignored raw report | `evaluation/results/qualitybench_v2_baseline_98db5679/eval_20261004T060418Z_877bd388bf34.json` |

This is the first successful complete live execution of all **72 test examples** (60 answerable, 12 unanswerable), with `repeat=1`. There were no technical restarts, repeated test questions, best-of-run selection, judge calls, or tuning. The original raw JSON remains unchanged locally; it is not committed. The [compact JSON](qualitybench_v2_baseline_v1.json) preserves its aggregates, identities, and deterministic diagnostic ledger.

## Exact configuration

| Setting | Resolved value |
| --- | --- |
| embedding_model_name | `BAAI/bge-small-en-v1.5` |
| embedding_device | `auto` |
| embedding_batch_size | `32` |
| embedding_normalize | `True` |
| default_top_k | `5` |
| bm25_k1 | `1.2` |
| bm25_b | `0.75` |
| rrf_k | `60` |
| dense_candidate_k | `20` |
| lexical_candidate_k | `20` |
| reranker_model_name | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| reranker_device | `auto` |
| reranker_batch_size | `8` |
| reranker_max_length | `512` |
| rerank_candidate_k | `20` |
| rerank_top_k | `8` |
| rerank_enabled | `True` |
| max_context_tokens | `1024` |
| llm_provider | `openai_compatible` |
| llm_model_name | `qwen2.5-coder:7b` |
| llm_base_url | `http://127.0.0.1:11434/v1` |
| llm_temperature | `0.0` |
| llm_max_output_tokens | `512` |
| llm_timeout_seconds | `120.0` |
| llm_response_format | `json_object` |
| llm_citation_repair | `True` |
| llm_format_repair | `False` |
| llm_keep_alive | (empty/default) |
| llm_repair_model_name | (empty/default) |
| conversation_window | `4` |

Chunking uses the default structure strategy: target 1,000 characters, maximum 1,500, minimum 200, overlap 150, with preferred section boundaries. Dense/lexical candidate depths are 20; hybrid/RRF candidates are reranked to 8. The full resolved Settings snapshot and exact evaluation config are in the compact JSON. Citation repair uses the same Qwen model; format repair is disabled.

| Identity | Value |
| --- | --- |
| chunker_id | `structure.v1:fc9ff956df32` |
| embedding_model_id | `bge-small-en-v1.5:73115d06b057` |
| index_id | `5a8ebe075cf9e5fb` |
| reranker_id | `ms-marco-MiniLM-L-6-v2:603b5a7fd2cf` |
| llm_id | `qwen2.5-coder-7b:8f6776b6b431` |
| resolver_id | `followup.heuristic.v4` |
| prompt_id | grounded.answerability.v5 |
| parser_id | json.object.v2 |

Executed once from the repository root:

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 /tmp/security-maintenance-gbyqcx71/test-env/bin/python -m research_assistant evaluate --dataset evaluation/datasets/qualitybench_v2.jsonl --corpus evaluation/corpus/quality_v2 --workspace evaluation/workspaces/qualitybench_v2_baseline_98db5679 --prepare --stage full --split test --mode hybrid --output evaluation/results/qualitybench_v2_baseline_98db5679
```

No application-setting environment overrides or logical differences from serving defaults were present. `PYTHONPATH=src` selects the checked-out source; `HF_HUB_OFFLINE=1` uses already-cached encoder weights without downloads. Neither changes the serving configuration. `--prepare` built a fresh isolated index; serving storage was not reused.

## Environment

Python 3.13.12, `Linux-7.0.0-34-generic-x86_64-with-glibc2.39`. CPU: 11th Gen Intel(R) Core(TM) i5-11260H @ 2.60GHz (12 logical CPUs). Ollama **0.21.0**, local loopback endpoint `http://127.0.0.1:11434/v1`; no cloud generation API. Model **qwen2.5-coder:7b**, 7.6B, Q4_K_M; digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`. No language model was pulled or substituted.

Both encoder models loaded successfully from cache with device `auto` resolving to **CUDA** on **NVIDIA GeForce RTX 3050 Laptop GPU**. The GPU has 4,096 MiB VRAM; driver 595.91.07; Torch CUDA 13.0. Ollama reported 2,565,965,824 bytes in VRAM out of 5,371,275,264 loaded bytes and a 4,096-token runtime context. This is partial GPU placement with system-memory use. No Ollama model was loaded before the run; the first generation includes a cold start.

Embedding revision: `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`. The evaluator reports the reranker revision as a model name; the separately recorded cached snapshot commit is `233902d25c440f23af6f7d6e94d2946bac0bee0a`. These are preserved separately rather than overstating the report identity.

| Package | Version |
| --- | --- |
| torch | 2.13.0 |
| sentence-transformers | 5.7.0 |
| transformers | 5.15.0 |
| numpy | 2.5.2 |
| qdrant-client | 1.19.0 |
| fastapi | 0.133.0 |
| starlette | 1.3.1 |
| pypdf | 6.19.0 |
| python-multipart | 0.0.32 |
| huggingface-hub | 1.27.0 |
| tokenizers | 0.22.2 |
| safetensors | 0.8.0 |
| scipy | 1.18.0 |
| scikit-learn | 1.9.0 |

The isolated Python environment satisfies the repository dependency requirements. No test suite or frontend build ran concurrently with the measurement. All 81 pre-existing serving-storage files and the frozen benchmark inputs were verified byte-for-byte unchanged.

## Overall results

| Product status | All (72) | Answerable (60) | Unanswerable (12) |
| --- | --- | --- | --- |
| GROUNDED | 40 | 39 | 1 |
| UNVERIFIED | 13 | 13 | 0 |
| NOT_ENOUGH_EVIDENCE | 19 | 8 | 11 |
| FORMAT_ERROR | 0 | 0 | 0 |
| TECHNICAL_ERROR | 0 | 0 | 0 |
| INVALID_CITATION | 0 | 0 | 0 |

Product `GROUNDED` means the production citation validator accepted the output; it does **not** establish semantic correctness or entailment. No composite accuracy score is reported.

## Retrieval → context funnel

| Metric | Result |
| --- | --- |
| gold_in_hybrid_rate | 100.00% |
| gold_in_rerank_rate | 100.00% |
| gold_chunk_selected_rate | 100.00% |
| context_gold_chunk_recall | 100.00% |
| rendered_gold_any_rate | 100.00% |
| rendered_gold_all_rate | 98.33% |
| rendered_gold_passage_recall | 99.17% |

| Cumulative gate | Entered | Retained | First exits |
| --- | --- | --- | --- |
| gold_retrieved | 60 | 60 | 0 |
| gold_survives_rerank | 60 | 60 | 0 |
| required_gold_rendered | 60 | 59 | 1 |
| answer_attempted | 59 | 52 | 7 |
| all_key_facts_matched | 52 | 37 | 15 |
| citation_valid | 37 | 32 | 5 |
| all_cited_gold_covered | 32 | 32 | 0 |

The funnel begins with 60 answerable items. Retrieval and rerank gates require **any labeled gold chunk**. Rendering and cited coverage require **all exact labeled gold passages** in source-matched excerpts. “Answer attempted” means parsed, non-abstaining output without a technical failure; the next gates require every lexical key fact, valid citation status, and full cited gold coverage. Each item exits once. Exit IDs and their original root causes are in the JSON. This stricter coverage funnel is distinct from the evaluator’s primary-failure taxonomy; the final retained count is not semantic accuracy.

## Answerability

| Metric | Result |
| --- | --- |
| true_positive | 11 |
| false_positive | 8 |
| false_negative | 1 |
| true_negative | 52 |
| precision | 57.89% |
| recall | 91.67% |
| false_answer_rate | 8.33% |
| false_abstention_rate | 13.33% |
| false_abstention_with_gold_context | 7 |

The positive class is **abstention / insufficient evidence**: TP is correct abstention on an unanswerable item; FP is abstention on an answerable item; FN is an attempted answer on an unanswerable item; TN is an answerable item not abstained. `false_abstention_with_gold_context` counts only cases where **all exact required gold passages were rendered**.

The seven all-gold-rendered abstentions include `qb2-021`, whose earlier primary label is `QUERY_REWRITE_ERROR`; the other six receive `FALSE_ABSTENTION_WITH_GOLD_CONTEXT`. The eighth answerable abstention, `qb2-089`, has incomplete rendered gold and primary `CONTEXT_BUDGET_DROP`.

## Answer content

| Metric | Result |
| --- | --- |
| lexical_key_fact_recall | 67.36% |
| all_lexical_key_facts_matched | 61.67% |
| reference_token_f1_diagnostic | 0.3601953306779927 |

Key-fact recall is averaged over answerable items. Reference token F1 is the evaluator’s diagnostic across all test rows, including unanswerable references. These metrics use lexical matching, not semantic entailment; a supported paraphrase can miss a label, and a wrong assertion can contain the label words.

## Citation behavior

| Metric | Result |
| --- | --- |
| answers_requiring_citation | 52 |
| answers_with_valid_citation | 39 |
| citation_coverage | 75.00% |
| missing_citation_count | 13 |
| invalid_citation_count | 0 |
| malformed_count | 0 |
| cited_gold_passage_recall | 64.17% |
| product_grounded | 40 |
| product_grounded_with_full_cited_gold | 38 |
| product_grounded_without_cited_gold | 0 |

| Metric | Result |
| --- | --- |
| product_grounded | 40 |
| full_gold_passage_coverage | 38 |
| partial_gold_passage_coverage | 1 |
| no_gold_passage_coverage | 0 |
| not_applicable | 1 |
| product_grounded_with_full_cited_gold | 38 |
| product_grounded_without_cited_gold | 0 |

Citation coverage uses non-abstaining, non-malformed answerable outputs as its denominator. Exact cited gold recall measures complete labeled passages inside cited rendered excerpts with matching source filenames. Valid citation IDs and full gold coverage do not prove that an answer’s claims follow from those passages.

## Conflict handling

| Metric | Result |
| --- | --- |
| n_expected_conflict | 6 |
| true_conflict_reported | 2 |
| true_conflict_both_key_facts | 2 |
| collapsed | 2 |
| incorrectly_abstained | 2 |
| false_conflict_reported | 0 |

These are overlapping diagnostics across six expected conflicts. “Reported” is a lexical disagreement marker; “both key facts” means recall 1.0. The aggregate “collapsed” flag means a parsed non-abstaining conflict answer lacks a disagreement marker. Primary `CONFLICT_HANDLING_FAILURE` separately detects one-sided lexical facts when all gold was rendered. Neither is a semantic judgment.

## Multi-source behavior

| Metric | Result |
| --- | --- |
| items_with_slots | 15 |
| all_slots_lexically_matched | 0 |
| all_slots_lexically_matched_rate | 0.00% |
| slot_count | 30 |
| slots_lexically_matched | 0 |
| lexical_slot_match_rate | 0.00% |
| slots_cited_gold | 11 |
| slot_cited_gold_rate | 36.67% |
| unmatched_labeled_slots | 30 |
| items_with_forbidden_phrase | 0 |

Slot metrics include every test item with authored claims, including conflict and multi-passage items. A slot matches only when the entire normalized authored claim phrase appears in the answer. These stricter phrases differ from compact key facts; unmatched slots are lexical diagnostics and cannot be read as missing semantic claims. Cited slot overlap separately checks the slot’s exact gold passage and source.

## Paraphrase stability

| Metric | Result |
| --- | --- |
| groups | 2 |
| stable_groups | 1 |
| consistency_rate | 50.00% |

| Group | n | Statuses | Distinct key-fact recall values | Stable |
| --- | --- | --- | --- | --- |
| meridian_final_score | 3 | GROUNDED | 1 | True |
| atlas_retired_status | 3 | UNVERIFIED | 2 | False |

Only the two test groups are measured; the third benchmark group belongs to dev. Stability requires the same product status and lexical key-fact recall across variants; it does not require identical answers or demonstrate semantic consistency.

## Citation repair

| Metric | Result |
| --- | --- |
| invocation_count | 31 |
| invocation_rate | 43.06% |
| repair_grounded_without_cited_gold | 0 |

| Drift kind | Count |
| --- | --- |
| added_factual_claim | 4 |
| entity_change | 4 |
| marker_only | 17 |
| paraphrase | 2 |
| polarity_change | 3 |

Drift kinds are the existing deterministic text-change diagnostics, not adjudicated semantic regressions. Invocation counts measure items that entered repair; rates use all 72 examples.

## Latency

Whole CLI wall time: **878.36 seconds** (14.64 minutes), from `2026-10-04T06:04:07.940548+00:00` to `2026-10-04T06:18:46.303785+00:00`. Mean reported LLM calls per example: **1.4306**.

| Stage (ms) | n | Mean | p50 | p95 | Cold first | Warm mean |
| --- | --- | --- | --- | --- | --- | --- |
| retrieval_ms | 72 | 31.91 | 30.97 | 37.15 | 30.15 | 31.93 |
| rerank_ms | 72 | 37.99 | 39.59 | 43.0 | 37.2 | 38.0 |
| generation_ms | 72 | 11894.62 | 8775.05 | 22778.39 | 78522.28 | 10956.2 |
| first_pass_generation_ms | 72 | 8055.59 | 6775.72 | 11186.82 | 71596.39 | 7160.65 |
| repair_ms | 72 | 3839.03 | 0.0 | 14279.32 | 6925.89 | 3795.55 |
| total_ms | 72 | 11964.52 | 8844.96 | 22852.96 | 78589.62 | 11026.13 |

Raw report summaries, including p90/min/max and warm medians, are preserved in JSON. “Warm” omits the first row; it is not a controlled warm-cache experiment. Row total sums evidence retrieval, reranker inference, and generation including repair. It excludes preparation, separate diagnostic searches, context/resolver overhead, and model loading outside those timers; it therefore differs from CLI wall time. Technical failures may have zero recorded generation time. Small slices have no p95 when the report’s sample threshold is unmet.

## Slice results

| Slice | n | Product counts | All gold rendered | Key-fact recall | False abstention | False answer | Citation coverage | Cited gold recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| conflict | 6 | G:2 / U:2 / N:2 / F:0 / T:0 / I:0 | 100.00% | 41.67% | 33.33% | n/a | 50.00% | 25.00% |
| core | 7 | G:4 / U:3 / N:0 / F:0 / T:0 / I:0 | 100.00% | 57.14% | 0.00% | n/a | 57.14% | 57.14% |
| followup | 6 | G:3 / U:0 / N:3 / F:0 / T:0 / I:0 | 100.00% | 50.00% | 50.00% | n/a | 100.00% | 50.00% |
| hard_negative | 4 | G:3 / U:1 / N:0 / F:0 / T:0 / I:0 | 100.00% | 100.00% | 0.00% | n/a | 75.00% | 75.00% |
| longdoc | 16 | G:14 / U:2 / N:0 / F:0 / T:0 / I:0 | 100.00% | 81.77% | 0.00% | n/a | 87.50% | 87.50% |
| multisource | 5 | G:2 / U:2 / N:1 / F:0 / T:0 / I:0 | 80.00% | 46.67% | 20.00% | n/a | 50.00% | 40.00% |
| paraphrase | 6 | G:3 / U:3 / N:0 / F:0 / T:0 / I:0 | 100.00% | 66.67% | 0.00% | n/a | 50.00% | 50.00% |
| subset | 5 | G:4 / U:0 / N:1 / F:0 / T:0 / I:0 | 100.00% | 70.00% | 20.00% | n/a | 100.00% | 80.00% |
| unanswerable | 12 | G:1 / U:0 / N:11 / F:0 / T:0 / I:0 | n/a | n/a | n/a | 8.33% | n/a | n/a |
| versioning | 5 | G:4 / U:0 / N:1 / F:0 / T:0 / I:0 | 100.00% | 80.00% | 20.00% | n/a | 100.00% | 80.00% |

Product keys: G=GROUNDED, U=UNVERIFIED, N=NOT_ENOUGH_EVIDENCE, F=FORMAT_ERROR, T=TECHNICAL_ERROR, I=INVALID_CITATION. Rates retain their original per-metric denominators; `n/a` means the denominator or applicable labels are absent. Full per-slice aggregates, including retrieval, repair, and latency, are in JSON.

| Slice | Primary failures |
| --- | --- |
| conflict | CONFLICT_HANDLING_FAILURE: 1, FALSE_ABSTENTION_WITH_GOLD_CONTEXT: 2, MISSING_CITATION: 2, WRONG_ANSWER: 1 |
| core | MISSING_CITATION: 1, WRONG_ANSWER: 3 |
| followup | FALSE_ABSTENTION_WITH_GOLD_CONTEXT: 2, QUERY_REWRITE_ERROR: 1 |
| hard_negative | MISSING_CITATION: 1 |
| longdoc | MULTISOURCE_SYNTHESIS_FAILURE: 2, WRONG_ANSWER: 2 |
| multisource | CONTEXT_BUDGET_DROP: 1, MISSING_CITATION: 1, MULTISOURCE_SYNTHESIS_FAILURE: 1, WRONG_ANSWER: 1 |
| paraphrase | INCOMPLETE_ANSWER: 2, WRONG_ANSWER: 1 |
| subset | FALSE_ABSTENTION_WITH_GOLD_CONTEXT: 1, INCOMPLETE_ANSWER: 1 |
| unanswerable | FALSE_ANSWER_WITHOUT_SUPPORT: 1 |
| versioning | FALSE_ABSTENTION_WITH_GOLD_CONTEXT: 1 |

## Failure distribution

| Existing primary failure | Count |
| --- | --- |
| WRONG_ANSWER | 8 |
| FALSE_ABSTENTION_WITH_GOLD_CONTEXT | 6 |
| MISSING_CITATION | 5 |
| INCOMPLETE_ANSWER | 3 |
| MULTISOURCE_SYNTHESIS_FAILURE | 3 |
| CONFLICT_HANDLING_FAILURE | 1 |
| CONTEXT_BUDGET_DROP | 1 |
| FALSE_ANSWER_WITHOUT_SUPPORT | 1 |
| QUERY_REWRITE_ERROR | 1 |
| No primary label | 43 |

The compact JSON contains **31 diagnostic-ledger entries**, ordered by example ID. It includes every existing primary/secondary failure and additional report-derived coverage/content/slot/repair/paraphrase flags. Successful marker-only repairs alone do not create failure entries. Thus its count can exceed the primary-failure count; a row with no primary label can still miss an exact gold passage or lexical claim phrase. Each entry retains the original taxonomy labels, product status, retrieval/rendered/cited metrics, repair count, latency, and a short field-derived note. No labels were manually reassigned.

Ledger inclusion rule: Include any existing primary/secondary failure; answerable non-grounded status, missing required rendered/cited gold, unmatched key facts; unanswerable non-abstention; forbidden-phrase hit; expected conflict without lexical conflict marker; unmatched/uncited claim slot; unstable paraphrase-group membership; or repair polarity/entity/added-claim drift. Successful marker-only repairs and lexical paraphrase drift alone do not trigger ledger inclusion. Supplemental diagnostic_reasons are report-derived flags, not rewritten root-cause labels or semantic judgments.

## Most important observations

The largest cumulative funnel exit is `all_key_facts_matched`: 15 of its 52 entering answerable items. The funnel retains 32 through all coverage/content/citation gates; this is not a semantic accuracy estimate.

The existing taxonomy's largest primary category is `WRONG_ANSWER` (8 items). The taxonomy and cumulative funnel have different gates and priorities, so their counts should not be conflated.

All exact gold is rendered for 98.33% of answerable items, compared with any-gold hybrid retrieval at 100.00%. There are 7 abstentions despite all required gold being rendered.

Of 40 product-grounded outputs, 38 have full exact cited gold and 0 have none. Key-fact and claim-slot scores remain lexical diagnostics.

Citation repair is invoked for 31/72 items. Its timing and text-drift diagnostics are reported separately from first-pass generation; no repair settings were changed in response.

These observations identify diagnostic areas for external review. No next experiment or implementation change is selected in this baseline PR.

## Limitations

This is one frozen run of a modest English-only, project-owned synthetic benchmark with four shared document families. It has no OCR, complex layout, multilingual, or real customer-document coverage. Within-split paraphrase/history/scope reuse reduces independence. There are no confidence intervals or repeated-run stability estimates. Temperature zero does not guarantee bitwise reproducibility across hardware or runtime versions.

Exact passage labels can miss valid alternative evidence; lexical key facts and authored claim phrases can miss correct paraphrases. Forbidden-phrase diagnostics can flag an obsolete value mentioned only to reject it. Valid citations and gold coverage do not establish entailment. Conflict detection is lexical. The primary taxonomy is ordered and may mask later failures; the ledger preserves additional diagnostics without relabeling roots. Synthetic benchmark results do not establish real-world product accuracy.

The first model request was cold, and Ollama used partial GPU placement on a 4 GiB laptop GPU. Background host activity was not controlled; the record captures observed timing, not a hardware-independent latency claim. The report’s timers omit some evaluator overhead, so wall time and reported latency should not be equated.

## Rules for future comparisons

- Keep benchmark test bytes frozen; verify the dataset and corpus hashes before comparison.
- Identify this baseline by source commit, raw run ID, and raw-report SHA-256. Keep the original raw file unchanged.
- Develop future experiments on **dev**. Use test only at deliberate, reviewed comparison checkpoints; never choose the best of repeated completed test runs.
- Keep models, cached model revisions, prompts, parser/resolver, index construction, and configuration constant unless that exact dimension is the experiment. Record dependency versions and the complete resolved environment.
- Do not directly compare changed metric schemas or silently replace benchmark labels.
- Compare latency on the same machine and runtime context, including model loading, GPU placement, cache state, and background load.
- Keep quality diagnostics and latency separate. Neither should be collapsed into an invented composite score.
- Do not tune in this baseline PR. External review precedes selection of a next experiment.
