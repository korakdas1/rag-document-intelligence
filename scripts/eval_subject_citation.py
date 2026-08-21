"""E027 subject completeness and citation-protocol compliance.

Uses GroundedGenerationService with fixed ContextBundles.
Does not change product defaults.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path

from research_assistant.evaluation.subjects import subject_completeness
from research_assistant.generation.citations import CITATION_RE, parse_model_output
from research_assistant.generation.factory import llm_from_settings
from research_assistant.generation.models import ValidationStatus
from research_assistant.generation.prompt import PROMPT_VERSION
from research_assistant.generation.service import GroundedGenerationService

_CITATION_EVAL = Path(__file__).with_name("eval_generation_citation.py")
_SPEC = importlib.util.spec_from_file_location("eval_generation_citation", _CITATION_EVAL)
assert _SPEC and _SPEC.loader
_CITATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CITATION)
_bundle = _CITATION._bundle
_settings = _CITATION._settings
summarize = _CITATION.summarize

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "datasets" / "genbench_subject_citation_v1.jsonl"
RESULTS = ROOT / "evaluation" / "results"


def _load(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            text = raw.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def _structured_ids(raw: str) -> list[str]:
    start = (raw or "").find("{")
    end = (raw or "").rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        payload = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    for key in ("citation_ids", "citations"):
        value = payload.get(key)
        if isinstance(value, list):
            return [str(item) for item in value if isinstance(item, str)]
    return []


def _inline_ids(text: str) -> list[str]:
    return [f"S{match.group(1)}" for match in CITATION_RE.finditer(text or "")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    args = parser.parse_args()
    examples = []
    for example in _load(args.dataset):
        item = dict(example)
        item["question"] = example.get("generation_question") or example["question"]
        item["original_question"] = example["question"]
        examples.append(item)
    RESULTS.mkdir(parents=True, exist_ok=True)
    print(f"running {args.model} n={len(examples)} label={args.label}")
    settings = _settings(args.model, repair=False)
    service = GroundedGenerationService(settings, llm=llm_from_settings(settings))
    traces: list[dict] = []
    started = time.perf_counter()
    subject_n = 0
    subject_ok = 0
    citation_in_raw_not_answer = 0
    structured_only = 0
    for example in examples:
        bundle = _bundle(settings, example["sources"], example["question"])
        expected_insuff = bool(example.get("expected_insufficient"))
        try:
            answer = service.generate(example["question"], bundle)
        except Exception as exc:  # noqa: BLE001
            traces.append(
                {
                    "example_id": example["example_id"],
                    "category": example.get("category"),
                    "validation_status": "provider_error",
                    "citation_count": 0,
                    "invalid_citation_ids": [],
                    "insufficient_evidence": False,
                    "repair_attempts": 0,
                    "generation_ms": 0.0,
                    "error": str(exc),
                    "expected_insufficient": expected_insuff,
                    "insufficient_ok": False,
                    "answer_preview": "",
                    "subject_complete": False,
                }
            )
            continue
        raw = answer.raw_response
        parsed = parse_model_output(raw)
        inline_answer = list(dict.fromkeys(_inline_ids(answer.answer_text)))
        inline_raw = list(dict.fromkeys(_inline_ids(raw)))
        structured = _structured_ids(raw)
        scored = bool(example.get("must_contain") or example.get("must_not_contain"))
        complete = subject_completeness(
            answer.answer_text,
            must_contain=example.get("must_contain") or (),
            must_not_contain=example.get("must_not_contain") or (),
            must_contain_any=bool(example.get("must_contain_any")),
        )
        if scored and not expected_insuff:
            subject_n += 1
            subject_ok += int(complete)
        if inline_raw and not inline_answer:
            citation_in_raw_not_answer += 1
        if structured and not inline_answer:
            structured_only += 1
        traces.append(
            {
                "example_id": example["example_id"],
                "category": example.get("category"),
                "validation_status": answer.validation_status.value,
                "citation_count": len(answer.citations),
                "invalid_citation_ids": list(answer.invalid_citation_ids),
                "insufficient_evidence": answer.insufficient_evidence,
                "repair_attempts": answer.diagnostics.repair_attempts,
                "generation_ms": answer.diagnostics.generation_ms,
                "expected_insufficient": expected_insuff,
                "insufficient_ok": (
                    answer.validation_status is ValidationStatus.INSUFFICIENT_EVIDENCE
                )
                is expected_insuff
                if expected_insuff or answer.insufficient_evidence
                else True,
                "answer_preview": answer.answer_text[:240],
                "generation_question": example["question"],
                "original_question": example.get("original_question"),
                "subject_complete": complete,
                "inline_citation_ids": inline_answer,
                "raw_inline_citation_ids": inline_raw,
                "structured_citation_ids": structured,
                "citation_in_raw_not_answer": bool(inline_raw and not inline_answer),
                "raw_preview": raw[:400],
                "parsed_malformed": parsed.malformed,
                "context_citation_ids": [item.citation_id for item in bundle.items],
            }
        )
    elapsed = (time.perf_counter() - started) * 1000
    metrics = summarize(traces)
    answerable = [row for row in traces if not row.get("expected_insufficient")]
    unanswerable = [row for row in traces if row.get("expected_insufficient")]
    metrics.update(
        {
            "wall_ms": elapsed,
            "model": args.model,
            "repair": False,
            "llm_id": service.identity().llm_id,
            "label": args.label,
            "prompt_version": PROMPT_VERSION,
            "subject_n": subject_n,
            "subject_complete": subject_ok,
            "subject_complete_rate": (subject_ok / subject_n) if subject_n else None,
            "answerable_n": len(answerable),
            "answerable_valid": sum(
                1 for row in answerable if row.get("validation_status") == "valid"
            ),
            "unanswerable_n": len(unanswerable),
            "unanswerable_abstained": sum(1 for row in unanswerable if row.get("insufficient_ok")),
            "citation_in_raw_not_answer": citation_in_raw_not_answer,
            "structured_citation_only": structured_only,
        }
    )
    payload = {"metrics": metrics, "traces": traces, "dataset": str(args.dataset)}
    out = RESULTS / (
        f"eval_e027_{args.label}_{args.model.replace(':', '_').replace('.', '')}.json"
    )
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
