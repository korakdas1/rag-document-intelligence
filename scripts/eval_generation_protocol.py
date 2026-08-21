"""Protocol-reliability evaluation on fixed ContextBundles.

Does not change retrieval. Writes evaluation/results/eval_e028_*.json.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from research_assistant.context.builder import CitationAwareContextBuilder
from research_assistant.core.settings import Settings
from research_assistant.generation.citations import PARSER_VERSION, parse_model_output
from research_assistant.generation.factory import llm_from_settings
from research_assistant.generation.models import ValidationStatus
from research_assistant.generation.prompt import PROMPT_VERSION
from research_assistant.generation.service import GroundedGenerationService
from research_assistant.retrieval.models import RetrievalHit

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "datasets" / "genbench_protocol_v1.jsonl"
RESULTS = ROOT / "evaluation" / "results"


def _settings(
    model: str,
    *,
    response_format: str,
    format_repair: bool,
) -> Settings:
    return Settings(
        database_path=ROOT / "data" / "processed" / "research_assistant.db",
        log_level="WARNING",
        max_file_bytes=50 * 1024 * 1024,
        llm_provider="openai_compatible",
        llm_model_name=model,
        llm_base_url="http://127.0.0.1:11434/v1",
        llm_temperature=0.0,
        llm_max_output_tokens=512,
        llm_timeout_seconds=120.0,
        llm_response_format=response_format,
        llm_citation_repair=False,
        llm_format_repair=format_repair,
        reranker_model_name="overlap",
    )


def _hit(index: int, filename: str, text: str) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=f"c{index}",
        document_id=f"d{index}",
        rank=index,
        score=0.2,
        retriever="hybrid",
        text=text,
        page_start=1,
        page_end=1,
        section_path=("Notes",),
        chunker_id="eval",
        index_id="eval",
        embedding_model_id="eval",
        filename=filename,
        content_hash=f"h{index}",
    )


def _bundle(settings: Settings, sources: list[dict[str, str]], question: str):
    hits = [
        _hit(index + 1, item["filename"], item["text"])
        for index, item in enumerate(sources)
    ]
    return CitationAwareContextBuilder(settings).build(hits, query=question)


def load_examples() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with DATASET.open(encoding="utf-8") as handle:
        for raw in handle:
            text = raw.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if len(values) < 20 and p >= 0.95:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return ordered[index]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows) or 1
    statuses: dict[str, int] = {}
    categories: dict[str, int] = {}
    parse_ok = 0
    for row in rows:
        statuses[row["validation_status"]] = statuses.get(row["validation_status"], 0) + 1
        categories[row.get("raw_output_category") or "unknown"] = (
            categories.get(row.get("raw_output_category") or "unknown", 0) + 1
        )
        if row.get("parse_success"):
            parse_ok += 1
    cited = sum(1 for row in rows if row["citation_count"] > 0)
    missing = statuses.get(ValidationStatus.MISSING_CITATIONS.value, 0)
    invalid = statuses.get(ValidationStatus.INVALID_CITATION.value, 0)
    malformed = statuses.get(ValidationStatus.MALFORMED_OUTPUT.value, 0)
    valid = statuses.get(ValidationStatus.VALID.value, 0)
    provider = sum(1 for row in rows if row["validation_status"] == "provider_error")
    timeout = sum(1 for row in rows if row.get("error_code") == "timeout")
    answerable = [row for row in rows if not row.get("expected_insufficient")]
    answerable_n = len(answerable) or 1
    insuff_rows = [row for row in rows if row.get("expected_insufficient")]
    insuff_ok = sum(
        1
        for row in insuff_rows
        if row["validation_status"] == ValidationStatus.INSUFFICIENT_EVIDENCE.value
    )
    latencies = [row["generation_ms"] for row in rows]
    latencies.sort()
    median = statistics.median(latencies) if latencies else None
    repair_n = sum(1 for row in rows if row.get("format_repair_attempted"))
    repair_ok = sum(1 for row in rows if row.get("format_repair_succeeded"))
    return {
        "n": len(rows),
        "parse_success_rate": parse_ok / n,
        "valid_output_rate": valid / n,
        "malformed_output_rate": malformed / n,
        "insufficient_evidence_valid_rate": (insuff_ok / len(insuff_rows)) if insuff_rows else None,
        "citation_presence_rate": cited / answerable_n,
        "invalid_citation_rate": invalid / n,
        "missing_citation_rate": missing / n,
        "provider_error_rate": provider / n,
        "timeout_count": timeout,
        "repair_attempt_rate": repair_n / n,
        "repair_success_rate": (repair_ok / repair_n) if repair_n else None,
        "status_counts": statuses,
        "raw_output_categories": categories,
        "median_generation_ms": median,
        "p95_generation_ms": _percentile(latencies, 0.95),
        "mean_generation_ms": (sum(latencies) / n) if rows else None,
    }


def run_model(
    model: str,
    examples: list[dict[str, Any]],
    *,
    repeats: int,
    response_format: str,
    format_repair: bool,
) -> dict[str, Any]:
    settings = _settings(
        model, response_format=response_format, format_repair=format_repair
    )
    llm = llm_from_settings(settings)
    service = GroundedGenerationService(settings, llm=llm)
    traces: list[dict[str, Any]] = []
    started = time.perf_counter()
    for example in examples:
        for repeat in range(repeats):
            bundle = _bundle(settings, example["sources"], example["question"])
            try:
                answer = service.generate(example["question"], bundle)
                parsed = parse_model_output(answer.raw_response)
                expected_insuff = bool(example.get("expected_insufficient"))
                traces.append(
                    {
                        "example_id": example["example_id"],
                        "repeat": repeat,
                        "category": example.get("category"),
                        "validation_status": answer.validation_status.value,
                        "parse_success": not parsed.malformed,
                        "raw_output_category": answer.diagnostics.raw_output_category,
                        "generation_protocol_status": answer.diagnostics.generation_protocol_status,
                        "normalization_applied": list(answer.diagnostics.normalization_applied),
                        "format_repair_attempted": answer.diagnostics.format_repair_attempted,
                        "format_repair_succeeded": answer.diagnostics.format_repair_succeeded,
                        "citation_count": len(answer.citations),
                        "invalid_citation_ids": list(answer.invalid_citation_ids),
                        "insufficient_evidence": answer.insufficient_evidence,
                        "generation_ms": answer.diagnostics.generation_ms,
                        "finish_reason": answer.diagnostics.finish_reason,
                        "expected_insufficient": expected_insuff,
                        "answer_preview": answer.answer_text[:240],
                        "raw_preview": (answer.raw_response or "")[:240],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                traces.append(
                    {
                        "example_id": example["example_id"],
                        "repeat": repeat,
                        "category": example.get("category"),
                        "validation_status": "provider_error",
                        "parse_success": False,
                        "raw_output_category": "empty_response",
                        "error": str(exc)[:300],
                        "error_code": getattr(exc, "code", None),
                        "citation_count": 0,
                        "invalid_citation_ids": [],
                        "insufficient_evidence": False,
                        "generation_ms": 0.0,
                        "expected_insufficient": bool(example.get("expected_insufficient")),
                        "answer_preview": "",
                        "raw_preview": "",
                        "format_repair_attempted": False,
                        "format_repair_succeeded": False,
                    }
                )
    elapsed = (time.perf_counter() - started) * 1000
    metrics = summarize(traces)
    metrics.update(
        {
            "wall_ms": elapsed,
            "model": model,
            "repeats": repeats,
            "temperature": 0.0,
            "prompt_version": PROMPT_VERSION,
            "parser_version": PARSER_VERSION,
            "response_format": response_format,
            "format_repair": format_repair,
            "citation_repair": False,
            "llm_id": service.identity().llm_id,
        }
    )
    return {"metrics": metrics, "traces": traces}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", dest="models")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--response-format", default="json_object")
    parser.add_argument("--format-repair", action="store_true")
    parser.add_argument("--tag", default="e028")
    args = parser.parse_args()
    models = args.models or ["qwen2.5-coder:7b"]
    examples = load_examples()
    RESULTS.mkdir(parents=True, exist_ok=True)
    combined: dict[str, Any] = {
        "dataset": str(DATASET),
        "prompt_version": PROMPT_VERSION,
        "parser_version": PARSER_VERSION,
        "models": {},
    }
    for model in models:
        print(f"running {model} n={len(examples)} repeats={args.repeats}")
        payload = run_model(
            model,
            examples,
            repeats=args.repeats,
            response_format=args.response_format,
            format_repair=args.format_repair,
        )
        combined["models"][model] = payload["metrics"]
        slug = model.replace(":", "_").replace(".", "")
        out = RESULTS / f"eval_{args.tag}_{slug}.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload["metrics"], indent=2))
        print(f"wrote {out}")
    combined_path = RESULTS / f"eval_{args.tag}_protocol_compare.json"
    combined_path.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {combined_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
