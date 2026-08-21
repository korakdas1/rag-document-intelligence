"""Evaluation runner uses production services. Hashing embedder; no network."""

import json
from pathlib import Path

from research_assistant.app import create_application
from research_assistant.chunking.config import default_config
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.evaluation.dataset import load_dataset, validate_dataset
from research_assistant.evaluation.gold import resolve_gold
from research_assistant.evaluation.prepare import prepare_corpus
from research_assistant.evaluation.runner import EvaluationRunner
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.reranking.overlap import OverlapReranker

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "evaluation" / "corpus"
DATASET = ROOT / "evaluation" / "datasets" / "ragbench_v1.jsonl"


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
    text = " ".join(message.content for message in request.messages)
    if "capital of France" in text or "president of France" in text:
        return json.dumps(
            {"answer": "Not enough evidence in the documents.", "insufficient_evidence": True}
        )
    return json.dumps(
        {
            "answer": "Self-attention computes a weighted combination of tokens [S1].",
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


def test_gold_resolves_for_structure_chunker(tmp_path: Path) -> None:
    app = _app(tmp_path)
    dataset = load_dataset(DATASET)
    validate_dataset(dataset, corpus_dir=CORPUS)
    prepared = prepare_corpus(app, CORPUS, chunking=default_config())
    answerable = [item for item in dataset.examples if item.answerable]
    for example in answerable:
        gold = resolve_gold(example, app.store, prepared["chunker_id"])
        assert gold.chunk_ids, example.example_id


def test_retrieval_metrics_are_deterministic(tmp_path: Path) -> None:
    app = _app(tmp_path)
    dataset = load_dataset(DATASET)
    prepared = prepare_corpus(app, CORPUS, chunking=default_config())
    runner = EvaluationRunner(app, dataset, chunker_id=prepared["chunker_id"])
    first = runner.run(stage="retrieval", mode="hybrid", split="dev", candidate_k=10)
    second = runner.run(stage="retrieval", mode="hybrid", split="dev", candidate_k=10)
    assert first["metrics"]["retrieval"] == second["metrics"]["retrieval"]
    assert first["metrics"]["retrieval"]["n"] == 12


def test_generation_stage_uses_scripted_llm(tmp_path: Path) -> None:
    app = _app(tmp_path)
    dataset = load_dataset(DATASET)
    prepared = prepare_corpus(app, CORPUS, chunking=default_config())
    runner = EvaluationRunner(app, dataset, chunker_id=prepared["chunker_id"])
    report = runner.run(stage="generation", mode="hybrid", split="dev", candidate_k=10)
    by_id = {row["example_id"]: row for row in report["examples"]}
    unans = by_id["dev-unans-paris"]
    assert unans["insufficient_evidence"] is True
    assert report["metrics"]["abstention"]["true_positive"] >= 1
    assert all("api_key" not in json.dumps(row.get("timings_ms")) for row in report["examples"])
