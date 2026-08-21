"""Score the heuristic follow-up resolver on ragbench_followup_v1. No LLM."""

from __future__ import annotations

import json
from pathlib import Path

from research_assistant.evaluation.followup import evaluate_resolver, load_followup_dataset

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "datasets" / "ragbench_followup_v1.jsonl"
OUT = ROOT / "evaluation" / "results" / "eval_e021_followup_heuristic.json"


def main() -> int:
    examples = load_followup_dataset(DATASET)
    summary = evaluate_resolver(examples)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "traces"}, indent=2))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
