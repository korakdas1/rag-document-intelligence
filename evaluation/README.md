# Evaluation

Synthetic, project-owned benchmarks. They measure retrieval, grounding, citations, abstention, and (optionally) local-model latency. They are **not** a general accuracy claim.

The public repository includes `ragbench_v1`, `qualitybench_v1`, the follow-up rewrite set, and small fixed-context genbench files used by optional scripts. Offline tests in `tests/` exercise the same pipeline with doubles.

## Suites

| Suite | Location | What it measures | Needs Ollama? |
| --- | --- | --- | --- |
| Offline pytest | `tests/` | Pipeline behavior with hashing embeddings, overlap/scripted rerank, `ScriptedLLM` | No |
| `ragbench_v1` | `evaluation/datasets/ragbench_v1.jsonl`, `evaluation/corpus/` (top-level files) | Retrieval and context construction | No for unit tests; yes for live model runs |
| `qualitybench_v1` | `evaluation/datasets/qualitybench_v1.jsonl`, `evaluation/corpus/quality/` | Answerability, citations, leaks, follow-ups (test **n=57**) | Yes for the published generation table |
| `ragbench_followup_v1` | `evaluation/datasets/ragbench_followup_v1.jsonl` | Query rewrite completeness (no generation) | No |

All corpora are original synthetic Markdown. Do not mix runtime uploads into these folders. Dataset notes: [datasets/README.md](datasets/README.md).

## Metrics (qualitybench_v1)

- **Gold in ContextBundle** — labeled gold passage reached the prompt context
- **False abstention with gold** — answerable item, gold in context, product status insufficient-evidence
- **False answer** — unanswerable item answered as if supported
- **GROUNDED / UNVERIFIED / NOT_ENOUGH_EVIDENCE** — product grounding states
- **Citation coverage** — valid `[S#]` among answerable non-abstaining answers that needed citations (**not** overall accuracy)
- **Invalid / malformed** — unknown IDs or unparseable model output
- **Lexical semantic support** — project audit of whether cited text supports the claim; not an NLI model

Published numbers: [docs/EVALUATION.md](../docs/EVALUATION.md).

## Offline / CI

```bash
python -m pytest
python -m compileall -q src tests scripts evaluation
```

These tests do not call Ollama, do not need a GPU, and do not download embedding weights.

## Optional live evaluation

Requires `qwen2.5-coder:7b` in Ollama plus Hugging Face embedding/reranker weights on first use. Runtime can be tens of minutes. Writes JSON under `evaluation/results/` (gitignored).

The existing CLI uses serving defaults. Example retrieval-only prepare-and-run on ragbench (uses the configured embedder, not the hashing test double):

```bash
python -m research_assistant evaluate \
  --dataset evaluation/datasets/ragbench_v1.jsonl \
  --corpus evaluation/corpus \
  --prepare \
  --stage retrieval
```

For qualitybench generation numbers, point `--dataset` at `evaluation/datasets/qualitybench_v1.jsonl` and `--corpus` at `evaluation/corpus/quality`. Do not treat a new run as production evidence unless configuration matches serving defaults.

## Limitations

Small English synthetic sets. Phrase-equivalent questions can still differ. A valid citation ID is not entailment. Conflict handling is weak. Local 7B latency dominates wall time.
