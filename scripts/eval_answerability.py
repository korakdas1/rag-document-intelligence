"""E026 answerability: fixed-context rubric cases and original-vs-resolved query A/B.

Uses GroundedGenerationService with the same ContextBundle builder as serving.
Does not change product defaults.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path

_CITATION_EVAL = Path(__file__).with_name("eval_generation_citation.py")
_SPEC = importlib.util.spec_from_file_location("eval_generation_citation", _CITATION_EVAL)
assert _SPEC and _SPEC.loader
_CITATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CITATION)
run_model = _CITATION.run_model
from research_assistant.generation.prompt import PROMPT_VERSION

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "datasets" / "genbench_answerability_v1.jsonl"
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


def _load(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            text = raw.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def _with_generation_question(examples: list[dict]) -> list[dict]:
    prepared: list[dict] = []
    for example in examples:
        item = dict(example)
        item["question"] = example.get("generation_question") or example["question"]
        item["original_question"] = example["question"]
        prepared.append(item)
    return prepared


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--product-snapshot", action="store_true")
    parser.add_argument("--skip-fixed", action="store_true")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    payload: dict = {"metrics": {"label": args.label, "model": args.model}, "traces": []}
    if not args.skip_fixed:
        examples = _with_generation_question(_load(args.dataset))
        print(f"running {args.model} n={len(examples)} label={args.label}")
        payload = run_model(args.model, examples, repair=False)
        for trace, example in zip(payload["traces"], examples, strict=True):
            trace["generation_question"] = example["question"]
            trace["original_question"] = example.get("original_question")
            trace["source_count"] = len(example.get("sources") or [])
        payload["metrics"].update(_classification(payload["traces"]))
        payload["metrics"]["label"] = args.label
        payload["metrics"]["prompt_version"] = PROMPT_VERSION
        payload["dataset"] = str(args.dataset)
        print(json.dumps(payload["metrics"], indent=2))
    if args.product_snapshot:
        payload["product_path"] = _product_path_compare(args.model)
        print(json.dumps(payload["product_path"]["summary"], indent=2))
    out = RESULTS / (
        f"eval_e026_{args.label}_{args.model.replace(':', '_').replace('.', '')}.json"
    )
    if args.skip_fixed and out.exists():
        existing = json.loads(out.read_text(encoding="utf-8"))
        existing["product_path"] = payload.get("product_path")
        payload = existing
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


def _product_path_compare(model: str) -> dict:
    """Compare product RAGService vs single-gold-chunk generation on the local index."""
    from research_assistant.app import create_application
    from research_assistant.context.builder import CitationAwareContextBuilder
    from research_assistant.conversation.models import ConversationTurn
    from research_assistant.core.settings import load_settings
    from research_assistant.generation.factory import llm_from_settings
    from research_assistant.generation.service import GroundedGenerationService
    from research_assistant.indexing.qdrant_store import qdrant_store_for
    from research_assistant.retrieval.models import RetrievalHit

    database = ROOT / "data" / "processed" / "research_assistant.db"
    index_path = ROOT / "data" / "indexes" / "qdrant"
    if not database.exists() or not index_path.exists():
        return {"summary": {"skipped": True, "reason": "no local product index"}}
    explicit = [
        "Do Harry Potter and Hermione Granger get together?",
        "Do Harry Potter and Hermione Granger marry?",
        "Is the ending happy for Harry Potter and Hermione Granger?",
        "When do Harry Potter and Hermione Granger marry?",
    ]
    session = [
        "Whose love story is this?",
        "Do they get together?",
        "Do they marry?",
        "Is it a happy ending?",
        "When do they marry?",
    ]
    gold_id = "2437dcd35e47e8dabd6db5a98240dbb3274596a63e7fb9fd6e1c04599376a2c1"
    with tempfile.TemporaryDirectory(prefix="rag-e026-") as raw:
        root = Path(raw)
        snap_db = root / database.name
        snap_index = root / "qdrant"
        shutil.copy2(database, snap_db)
        shutil.copytree(index_path, snap_index)
        settings = load_settings(
            database_path=snap_db,
            vector_index_path=snap_index,
            llm_model_name=model,
        )
        app = create_application(settings)
        llm = llm_from_settings(settings)
        isolated = GroundedGenerationService(settings, llm=llm)
        gold = app.store.get_chunk(gold_id)
        traces: list[dict] = []
        session_traces: list[dict] = []
        try:
            if gold is None:
                return {"summary": {"skipped": True, "reason": "gold chunk missing"}}
            chunker_id = gold.chunker_id
            gold_hit = RetrievalHit(
                chunk_id=gold.chunk_id,
                document_id=gold.document_id,
                rank=1,
                score=1.0,
                retriever="hybrid",
                text=gold.text,
                page_start=gold.page_start,
                page_end=gold.page_end,
                section_path=gold.section_path,
                chunker_id=gold.chunker_id,
                index_id="eval",
                embedding_model_id="eval",
                filename="Enough_is_enough_by_broomstick_flyer-MKLSdo6F.pdf",
                content_hash=gold.content_hash,
            )
            gold_bundle = CitationAwareContextBuilder(settings).build(
                [gold_hit], query="gold"
            )
            for question in explicit:
                traces.append(
                    _compare_row(
                        question,
                        app.rag.answer(question, chunker_id=chunker_id),
                        isolated.generate(question, gold_bundle),
                        gold_id,
                    )
                )
            history: list[ConversationTurn] = []
            for question in session:
                product = app.rag.answer(
                    question,
                    chunker_id=chunker_id,
                    conversation=tuple(history),
                )
                session_traces.append(
                    _compare_row(
                        question,
                        product,
                        isolated.generate(product.query, gold_bundle),
                        gold_id,
                    )
                )
                history.append(
                    ConversationTurn(
                        question=question,
                        answer=product.answer.answer_text,
                        grounding_status=product.answer.validation_status.value,
                        sequence=len(history) + 1,
                    )
                )
        finally:
            qdrant_store_for(snap_index).close()
    product_false_abs = sum(
        1
        for row in traces
        if row["gold_in_product_context"] and row["product_insufficient"]
    )
    isolated_false_abs = sum(1 for row in traces if row["isolated_gold_insufficient"])
    session_false_abs = sum(
        1
        for row in session_traces
        if row["gold_in_product_context"] and row["product_insufficient"]
    )
    return {
        "summary": {
            "n": len(traces),
            "product_false_abstention_with_gold_in_context": product_false_abs,
            "isolated_gold_false_abstention": isolated_false_abs,
            "session_n": len(session_traces),
            "session_false_abstention_with_gold_in_context": session_false_abs,
        },
        "traces": traces,
        "session_traces": session_traces,
    }


def _compare_row(question, product, isolated_answer, gold_id: str) -> dict:
    return {
        "question": question,
        "original_question": product.original_query,
        "generation_question": product.query,
        "product_status": product.answer.validation_status.value,
        "product_insufficient": product.answer.insufficient_evidence,
        "product_citation_ids": [
            item.citation_id for item in product.evidence.context.items
        ],
        "gold_in_product_context": any(
            item.source.chunk_id == gold_id
            for item in product.evidence.context.items
        ),
        "isolated_gold_status": isolated_answer.validation_status.value,
        "isolated_gold_insufficient": isolated_answer.insufficient_evidence,
        "product_preview": product.answer.answer_text[:240],
        "isolated_preview": isolated_answer.answer_text[:240],
    }


if __name__ == "__main__":
    raise SystemExit(main())
