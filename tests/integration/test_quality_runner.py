"""Qualitybench runner uses production services with hashing/scripted fakes."""

import json
from pathlib import Path

from research_assistant.app import create_application
from research_assistant.chunking.config import default_config
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.evaluation.dataset import load_dataset, validate_dataset
from research_assistant.evaluation.gold import resolve_gold
from research_assistant.evaluation.prepare import prepare_corpus
from research_assistant.evaluation.quality_runner import QualityEvaluationRunner, write_citation_review_csv
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.reranking.overlap import OverlapReranker

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "evaluation" / "corpus" / "quality"
DATASET = ROOT / "evaluation" / "datasets" / "qualitybench_v1.jsonl"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "eval.db",
        log_level="WARNING",
        max_file_bytes=50 * 1024 * 1024,
        embedding_model_name="hashing",
        embedding_device="cpu",
        vector_index_path=tmp_path / "qdrant",
        default_top_k=10,
        dense_candidate_k=10,
        lexical_candidate_k=10,
        reranker_model_name="overlap",
        rerank_enabled=True,
        rerank_candidate_k=10,
        rerank_top_k=5,
        max_context_tokens=512,
        llm_provider="scripted",
        llm_model_name="scripted.v1",
    )


def _scripted(request) -> str:
    text = " ".join(message.content for message in request.messages).lower()
    leak = (
        "capital of france",
        "eiffel",
        "speed of light",
        "telephone",
        "adult fare",
        "ceo of riverton",
        "when did it launch",
    )
    if any(item in text for item in leak):
        return json.dumps(
            {"answer": "Not enough evidence in the documents.", "insufficient_evidence": True}
        )
    return json.dumps(
        {
            "answer": "The revenue fleet contains 42 vehicles [S1].",
            "insufficient_evidence": False,
        }
    )


def _app(tmp_path: Path):
    return create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=ScriptedLLM(_scripted),
    )


def test_quality_gold_resolves(tmp_path: Path) -> None:
    app = _app(tmp_path)
    dataset = load_dataset(DATASET)
    validate_dataset(dataset, corpus_dir=CORPUS)
    prepared = prepare_corpus(app, CORPUS, chunking=default_config())
    for example in dataset.examples:
        if not example.answerable:
            continue
        gold = resolve_gold(example, app.store, prepared["chunker_id"])
        assert gold.chunk_ids, example.example_id


def test_quality_runner_scripted_full_dev(tmp_path: Path) -> None:
    app = _app(tmp_path)
    dataset = load_dataset(DATASET)
    prepared = prepare_corpus(app, CORPUS, chunking=default_config())
    runner = QualityEvaluationRunner(app, dataset, chunker_id=prepared["chunker_id"])
    report = runner.run(stage="full", split="dev", output_dir=tmp_path / "out")
    assert report["config"]["family"] == "qualitybench"
    assert report["metrics"]["n"] == 6
    assert "primary_failures" in report["metrics"]
    assert (tmp_path / "out" / f"{report['run_id']}.json").is_file()
    csv_path = tmp_path / "review.csv"
    write_citation_review_csv(report, csv_path)
    assert csv_path.is_file()
    body = csv_path.read_text(encoding="utf-8")
    assert "question_id" in body
    leak = next(item for item in report["examples"] if item["example_id"] == "qb-dev-unans-paris")
    assert leak["insufficient_evidence"] is True
    fleet = next(item for item in report["examples"] if item["example_id"] == "qb-dev-fleet")
    assert fleet["resolved_query"]
    assert "timings_ms" in fleet


def test_quality_runner_example_ids_filter(tmp_path: Path) -> None:
    app = _app(tmp_path)
    dataset = load_dataset(DATASET)
    prepared = prepare_corpus(app, CORPUS, chunking=default_config())
    runner = QualityEvaluationRunner(app, dataset, chunker_id=prepared["chunker_id"])
    report = runner.run(
        stage="full",
        split="dev",
        example_ids=["qb-dev-fleet", "qb-dev-unans-paris"],
    )
    assert report["metrics"]["n"] == 2
    assert {item["example_id"] for item in report["examples"]} == {
        "qb-dev-fleet",
        "qb-dev-unans-paris",
    }


def test_quality_runner_respects_filename_filter(tmp_path: Path) -> None:
    app = _app(tmp_path)
    dataset = load_dataset(DATASET)
    prepared = prepare_corpus(app, CORPUS, chunking=default_config())
    runner = QualityEvaluationRunner(app, dataset, chunker_id=prepared["chunker_id"])
    report = runner.run(stage="context", split="test")
    subset_wrong = next(item for item in report["examples"] if item["example_id"] == "qb-subset-wrong")
    assert subset_wrong["selected_filenames"] == ["pebble_kit.md"]
    docs = {record.document_id: record.filename for record in app.store.list_documents()}
    overview_ids = {
        chunk.chunk_id
        for chunk in app.store.list_chunks_for_chunker(prepared["chunker_id"])
        if docs.get(chunk.document_id) == "riverton_overview.md"
    }
    assert not set(subset_wrong["hybrid_ids"]) & overview_ids
