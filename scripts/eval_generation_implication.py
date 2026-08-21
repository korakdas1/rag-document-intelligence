"""Fixed-context implication vs abstention check for grounded generation.

Does not change product defaults. Writes evaluation/results/eval_e025_*.json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

_CITATION_EVAL = Path(__file__).with_name("eval_generation_citation.py")
_SPEC = importlib.util.spec_from_file_location("eval_generation_citation", _CITATION_EVAL)
assert _SPEC and _SPEC.loader
_CITATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CITATION)
run_model = _CITATION.run_model

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "datasets" / "genbench_implication_v1.jsonl"
RESULTS = ROOT / "evaluation" / "results"


def _classification(traces: list[dict]) -> dict[str, float | int | None]:
    answerable = [row for row in traces if not row.get("expected_insufficient")]
    unanswerable = [row for row in traces if row.get("expected_insufficient")]
    answerable_ok = sum(
        1
        for row in answerable
        if not row.get("insufficient_evidence")
        and row.get("validation_status") != "provider_error"
    )
    unanswerable_ok = sum(1 for row in unanswerable if row.get("insufficient_ok"))
    return {
        "answerable_n": len(answerable),
        "answerable_not_abstained": answerable_ok,
        "answerable_not_abstained_rate": (
            answerable_ok / len(answerable) if answerable else None
        ),
        "unanswerable_n": len(unanswerable),
        "unanswerable_abstained": unanswerable_ok,
        "unanswerable_abstained_rate": (
            unanswerable_ok / len(unanswerable) if unanswerable else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--label", default="postfix")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    args = parser.parse_args()
    examples = _load(args.dataset)
    RESULTS.mkdir(parents=True, exist_ok=True)
    print(f"running {args.model} n={len(examples)} label={args.label}")
    payload = run_model(args.model, examples, repair=False)
    payload["metrics"].update(_classification(payload["traces"]))
    payload["metrics"]["label"] = args.label
    payload["dataset"] = str(args.dataset)
    out = RESULTS / f"eval_e025_{args.label}_{args.model.replace(':', '_').replace('.', '')}.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["metrics"], indent=2))
    print(f"wrote {out}")
    return 0


def _load(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            text = raw.strip()
            if text:
                rows.append(json.loads(text))
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
