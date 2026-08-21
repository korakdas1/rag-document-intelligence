"""Compare local Ollama models on citation-protocol compliance.

Uses fixed ContextBundles so retrieval is not in the loop.
Does not change product defaults. Writes evaluation/results/eval_e022_*.json.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from research_assistant.context.builder import CitationAwareContextBuilder
from research_assistant.core.settings import Settings
from research_assistant.generation.factory import llm_from_settings
from research_assistant.generation.models import ValidationStatus
from research_assistant.generation.service import GroundedGenerationService
from research_assistant.retrieval.models import RetrievalHit

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "datasets" / "genbench_citation_v1.jsonl"
RESULTS = ROOT / "evaluation" / "results"


def _settings(model: str, *, repair: bool = False) -> Settings:
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
        llm_citation_repair=repair,
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


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows) or 1
    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row["validation_status"]] = statuses.get(row["validation_status"], 0) + 1
    cited = sum(1 for row in rows if row["citation_count"] > 0)
    missing = statuses.get(ValidationStatus.MISSING_CITATIONS.value, 0)
    invalid = statuses.get(ValidationStatus.INVALID_CITATION.value, 0)
    malformed = statuses.get(ValidationStatus.MALFORMED_OUTPUT.value, 0)
    valid = statuses.get(ValidationStatus.VALID.value, 0)
    insuff = statuses.get(ValidationStatus.INSUFFICIENT_EVIDENCE.value, 0)
    insuff_ok = sum(1 for row in rows if row.get("expected_insufficient") and row["insufficient_ok"])
    insuff_n = sum(1 for row in rows if row.get("expected_insufficient"))
    latencies = [row["generation_ms"] for row in rows]
    latencies.sort()
    median = latencies[len(latencies) // 2] if latencies else None
    return {
        "n": len(rows),
        "valid_output_rate": valid / n,
        "citation_coverage": cited / n,
        "missing_citation_rate": missing / n,
        "invalid_citation_count": invalid,
        "malformed_output_rate": malformed / n,
        "insufficient_evidence_correct": (insuff_ok / insuff_n) if insuff_n else None,
        "insufficient_status_count": insuff,
        "status_counts": statuses,
        "median_generation_ms": median,
        "mean_generation_ms": sum(latencies) / n if rows else None,
    }


def run_model(model: str, examples: list[dict[str, Any]], *, repair: bool = False) -> dict[str, Any]:
    settings = _settings(model, repair=repair)
    llm = llm_from_settings(settings)
    service = GroundedGenerationService(settings, llm=llm)
    traces: list[dict[str, Any]] = []
    started = time.perf_counter()
    for example in examples:
        bundle = _bundle(settings, example["sources"], example["question"])
        try:
            answer = service.generate(example["question"], bundle)
            expected_insuff = bool(example.get("expected_insufficient"))
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
                }
            )
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
                    "expected_insufficient": bool(example.get("expected_insufficient")),
                    "insufficient_ok": False,
                    "answer_preview": "",
                }
            )
    elapsed = (time.perf_counter() - started) * 1000
    metrics = summarize(traces)
    metrics["wall_ms"] = elapsed
    metrics["model"] = model
    metrics["repair"] = repair
    metrics["llm_id"] = service.identity().llm_id
    return {"metrics": metrics, "traces": traces}


def main() -> int:
    examples = load_examples()
    models = ["llama3.2", "qwen2.5-coder:7b"]
    RESULTS.mkdir(parents=True, exist_ok=True)
    combined: dict[str, Any] = {"dataset": str(DATASET), "models": {}}
    for model in models:
        print(f"running {model} n={len(examples)}")
        payload = run_model(model, examples, repair=False)
        combined["models"][model] = payload["metrics"]
        out = RESULTS / f"eval_e022_{model.replace(':', '_').replace('.', '')}.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload["metrics"], indent=2))
        print(f"wrote {out}")
    combined_path = RESULTS / "eval_e022_generation_citation_compare.json"
    combined_path.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {combined_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
