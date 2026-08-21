"""Evaluation runner over production HybridSearchService / EvidencePipeline / generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_assistant.app import Application
from research_assistant.context.models import ContextBundle
from research_assistant.core.errors import EvaluationError
from research_assistant.core.types import RetrievalMode
from research_assistant.evaluation.aggregate import (
    abstention_summary,
    by_category,
    citation_summary,
    context_summary,
    contribution_summary,
    failure_summary,
    latency_summary,
    retrieval_table,
)
from research_assistant.evaluation.cache import GenerationCache, cache_key, context_identity
from research_assistant.evaluation.gold import contribution_label, resolve_gold
from research_assistant.evaluation.identity import git_commit, make_run_id, utc_stamp
from research_assistant.evaluation.judge import evaluator_id, judge_answer
from research_assistant.evaluation.metrics import (
    hit_rate_at_k,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    token_f1,
)
from research_assistant.evaluation.models import (
    EvalStage,
    EvaluationDataset,
    EvaluationExample,
    ExampleTrace,
    RetrievalScores,
    Split,
)
from research_assistant.evaluation.taxonomy import classify
from research_assistant.generation.models import GroundedAnswer, ValidationStatus
from research_assistant.generation.protocol import LLMClient
from research_assistant.retrieval.models import RetrievalHit


class EvaluationRunner:
    def __init__(
        self,
        app: Application,
        dataset: EvaluationDataset,
        *,
        chunker_id: str,
        cache_dir: Path | None = None,
        judge: LLMClient | None = None,
    ) -> None:
        self._app = app
        self._dataset = dataset
        self._chunker_id = chunker_id
        self._cache = GenerationCache(cache_dir)
        self._judge = judge

    def run(
        self,
        *,
        stage: str = EvalStage.RETRIEVAL.value,
        mode: str = RetrievalMode.HYBRID.value,
        split: str | None = Split.TEST.value,
        candidate_k: int | None = None,
        rerank_top_k: int | None = None,
        max_context_tokens: int | None = None,
        output_dir: Path | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            resolved_stage = EvalStage(stage)
        except ValueError as exc:
            raise EvaluationError(f"Unknown evaluation stage {stage!r}", code="invalid_stage") from exc
        examples = self._dataset.filter_split(split)
        if not examples:
            raise EvaluationError("No examples in the requested split", code="empty_split")
        settings = self._app.settings
        pool_k = candidate_k if candidate_k is not None else settings.rerank_candidate_k
        config = {
            "dataset_id": self._dataset.dataset_id,
            "dataset_version": self._dataset.version,
            "stage": resolved_stage.value,
            "mode": mode,
            "split": split,
            "chunker_id": self._chunker_id,
            "candidate_k": pool_k,
            "dense_candidate_k": settings.dense_candidate_k,
            "lexical_candidate_k": settings.lexical_candidate_k,
            "rrf_k": settings.rrf_k,
            "rerank_enabled": settings.rerank_enabled,
            "reranker_model": settings.reranker_model_name,
            "rerank_top_k": rerank_top_k if rerank_top_k is not None else settings.rerank_top_k,
            "max_context_tokens": max_context_tokens
            if max_context_tokens is not None
            else settings.max_context_tokens,
            "embedding_model": settings.embedding_model_name,
            "llm_model": settings.llm_model_name,
            "llm_provider": settings.llm_provider,
        }
        stamp = utc_stamp()
        rid = run_id or make_run_id(config, stamp=stamp)
        traces = [
            self._evaluate_one(
                example,
                stage=resolved_stage,
                mode=mode,
                pool_k=pool_k,
                rerank_top_k=int(config["rerank_top_k"]),
                max_context_tokens=int(config["max_context_tokens"]),
            )
            for example in examples
        ]
        report = {
            "run_id": rid,
            "date": stamp,
            "git_commit": git_commit(),
            "config": config,
            "identities": self._identities(),
            "metrics": self._metrics(traces, examples, resolved_stage),
            "examples": [trace.to_dict() for trace in traces],
        }
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / f"{rid}.json"
            path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            report["output_path"] = str(path)
        return report

    def _evaluate_one(
        self,
        example: EvaluationExample,
        *,
        stage: EvalStage,
        mode: str,
        pool_k: int,
        rerank_top_k: int,
        max_context_tokens: int,
    ) -> ExampleTrace:
        gold = resolve_gold(example, self._app.store, self._chunker_id)
        dense = self._app.hybrid.search(
            example.question,
            chunker_id=self._chunker_id,
            mode=RetrievalMode.DENSE.value,
            top_k=pool_k,
        )
        lexical = self._app.hybrid.search(
            example.question,
            chunker_id=self._chunker_id,
            mode=RetrievalMode.LEXICAL.value,
            top_k=pool_k,
        )
        primary = self._app.hybrid.search(
            example.question,
            chunker_id=self._chunker_id,
            mode=mode,
            top_k=pool_k,
        )
        dense_ids = _ids(dense.hits)
        lexical_ids = _ids(lexical.hits)
        primary_ids = _ids(primary.hits)
        trace = ExampleTrace(
            example_id=example.example_id,
            question=example.question,
            split=example.split.value,
            category=example.category,
            expected_chunk_ids=sorted(gold.chunk_ids),
            expected_filenames=list(example.relevant_filenames),
            dense_ids=dense_ids,
            lexical_ids=lexical_ids,
            hybrid_ids=primary_ids,
            contribution=contribution_label(gold.chunk_ids, dense_ids, lexical_ids),
            retrieval_scores=_score_list(
                primary_ids, gold.chunk_ids, primary.hits, gold.document_ids
            ).to_dict(),
            timings_ms={
                "dense_ms": dense.diagnostics.total_ms,
                "lexical_ms": lexical.diagnostics.total_ms,
                "fusion_ms": primary.diagnostics.fusion_ms,
                "retrieval_ms": primary.diagnostics.total_ms,
            },
            candidate_recall=recall_at_k(primary_ids, gold.chunk_ids, pool_k),
        )
        if stage is EvalStage.RETRIEVAL:
            trace.failure_categories = classify(example, trace, top_k=min(10, pool_k))
            trace.timings_ms["total_ms"] = trace.timings_ms["retrieval_ms"]
            return trace

        evidence = self._app.evidence.collect(
            example.question,
            chunker_id=self._chunker_id,
            mode=mode,
            candidate_k=pool_k,
            rerank_top_k=rerank_top_k,
            max_context_tokens=max_context_tokens,
        )
        rerank_ids = _ids(evidence.rerank.hits)
        context_ids = [item.source.chunk_id for item in evidence.context.items]
        trace.rerank_ids = rerank_ids
        trace.rerank_scores = _score_list(
            rerank_ids, gold.chunk_ids, evidence.rerank.hits, gold.document_ids
        ).to_dict()
        trace.context_chunk_ids = context_ids
        trace.context_citation_ids = [item.citation_id for item in evidence.context.items]
        trace.context_gold_hit = bool(gold.chunk_ids & set(context_ids)) if gold.chunk_ids else None
        denom = max(len(context_ids), 1)
        trace.context_evidence_recall = recall_at_k(context_ids, gold.chunk_ids, denom)
        trace.timings_ms["rerank_ms"] = evidence.rerank.diagnostics.inference_ms
        trace.timings_ms["retrieval_ms"] = evidence.search.diagnostics.total_ms
        if stage in {EvalStage.RERANK, EvalStage.CONTEXT}:
            trace.failure_categories = classify(example, trace, top_k=min(10, pool_k))
            trace.timings_ms["total_ms"] = (
                trace.timings_ms["retrieval_ms"] + trace.timings_ms["rerank_ms"]
            )
            return trace

        cached_payload, answer, cited_ids = self._generate(example.question, evidence.context)
        trace.answer_text = answer.answer_text
        trace.validation_status = answer.validation_status.value
        trace.insufficient_evidence = answer.insufficient_evidence
        trace.cited_chunk_ids = list(cited_ids)
        trace.invalid_citation_ids = list(answer.invalid_citation_ids)
        trace.reference_token_f1 = token_f1(answer.answer_text, example.reference_answer or "")
        trace.lexical_citation_support = _citation_support(
            example, cited_ids, self._app.store
        )
        trace.cached_generation = cached_payload
        trace.timings_ms["generation_ms"] = answer.diagnostics.generation_ms
        trace.timings_ms["total_ms"] = (
            trace.timings_ms["retrieval_ms"]
            + trace.timings_ms.get("rerank_ms", 0.0)
            + answer.diagnostics.generation_ms
        )
        if self._judge is not None:
            trace.judge = judge_answer(
                self._judge,
                question=example.question,
                answer_text=answer.answer_text,
                evidence_text=evidence.context.rendered_text,
            )
        trace.failure_categories = classify(example, trace, top_k=min(10, pool_k))
        return trace

    def _generate(
        self, question: str, bundle: ContextBundle
    ) -> tuple[bool, GroundedAnswer, tuple[str, ...]]:
        identity = self._app.generation.identity()
        ctx_id = context_identity(
            bundle.rendered_text,
            tuple(item.citation_id for item in bundle.items),
        )
        key = cache_key(identity.llm_id, question, ctx_id)
        hit = self._cache.get(key)
        if hit is not None:
            status = ValidationStatus(hit["validation_status"])
            cached = GroundedAnswer(
                question=question,
                answer_text=hit["answer_text"],
                citations=(),
                invalid_citation_ids=tuple(hit.get("invalid_citation_ids") or ()),
                insufficient_evidence=bool(hit["insufficient_evidence"]),
                validation_status=status,
                diagnostics=answer_diagnostics_from_cache(
                    hit, identity.llm_id, identity.provider, identity.model_name
                ),
                raw_response=hit.get("raw_response") or "",
            )
            return True, cached, tuple(hit.get("cited_chunk_ids") or ())
        answer = self._app.generation.generate(question, bundle)
        cited = tuple(item.source.chunk_id for item in answer.citations)
        self._cache.put(
            key,
            {
                "question": question,
                "answer_text": answer.answer_text,
                "insufficient_evidence": answer.insufficient_evidence,
                "validation_status": answer.validation_status.value,
                "invalid_citation_ids": list(answer.invalid_citation_ids),
                "cited_chunk_ids": list(cited),
                "generation_ms": answer.diagnostics.generation_ms,
                "raw_response": answer.raw_response,
                "llm_id": identity.llm_id,
                "context_id": ctx_id,
            },
        )
        return False, answer, cited

    def _identities(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chunker_id": self._chunker_id,
            "embedding_model_id": self._app.indexing.embedder.identity.embedding_model_id,
            "index_id": self._app.indexing.index_id_for_chunker(self._chunker_id),
        }
        try:
            payload["reranker_id"] = self._app.reranker.identity().reranker_id
        except Exception:  # noqa: BLE001
            payload["reranker_id"] = None
        try:
            payload["llm_id"] = self._app.generation.identity().llm_id
        except Exception:  # noqa: BLE001
            payload["llm_id"] = None
        if self._judge is not None:
            payload["evaluator_id"] = evaluator_id(self._judge.identity)
        return payload

    def _metrics(
        self,
        traces: list[ExampleTrace],
        examples: tuple[EvaluationExample, ...],
        stage: EvalStage,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "retrieval": retrieval_table(traces, "retrieval_scores"),
            "retrieval_by_category": by_category(traces, "retrieval_scores"),
            "hybrid_contribution": contribution_summary(traces),
            "latency": latency_summary(traces),
            "failures": failure_summary(traces),
        }
        if stage in {EvalStage.RERANK, EvalStage.CONTEXT, EvalStage.GENERATION, EvalStage.FULL}:
            payload["rerank"] = retrieval_table(traces, "rerank_scores")
            payload["context"] = context_summary(traces)
        if stage in {EvalStage.GENERATION, EvalStage.FULL}:
            payload["citations"] = citation_summary(traces, examples)
            payload["abstention"] = abstention_summary(traces, examples)
            payload["reference_token_f1"] = mean(
                [trace.reference_token_f1 for trace in traces]
            )
        return payload


def _citation_support(
    example: EvaluationExample,
    cited_chunk_ids: tuple[str, ...] | list[str],
    store,
) -> float | None:
    if not cited_chunk_ids:
        return None
    needles = [_normalize(passage.text) for passage in example.gold_passages]
    if not needles:
        return None
    supported = 0
    for chunk_id in cited_chunk_ids:
        chunk = store.get_chunk(chunk_id)
        if chunk is None:
            continue
        body = _normalize(chunk.text)
        if any(text in body for text in needles):
            supported += 1
    return supported / len(cited_chunk_ids)


def answer_diagnostics_from_cache(
    hit: dict[str, Any],
    llm_id: str,
    provider: str,
    model_name: str,
):
    from research_assistant.generation.models import GenerationDiagnostics

    return GenerationDiagnostics(
        llm_id=llm_id,
        provider=provider,
        model_name=model_name,
        generation_ms=float(hit.get("generation_ms") or 0.0),
        estimated_input_tokens=0,
        provider_input_tokens=None,
        provider_output_tokens=None,
        finish_reason="cache",
        citation_count=len(hit.get("cited_chunk_ids") or []),
        invalid_citation_ids=tuple(hit.get("invalid_citation_ids") or ()),
        malformed_markers=(),
        repair_attempts=0,
        insufficient_evidence=bool(hit["insufficient_evidence"]),
        empty_context_short_circuit=False,
        provider_request_id=None,
        validation_status=str(hit["validation_status"]),
    )


def _ids(hits: tuple[RetrievalHit, ...]) -> list[str]:
    return [hit.chunk_id for hit in hits]


def _score_list(
    retrieved_ids: list[str],
    gold_chunks: set[str],
    hits: tuple[RetrievalHit, ...],
    gold_documents: set[str],
) -> RetrievalScores:
    doc_ids = [hit.document_id for hit in hits]
    return RetrievalScores(
        recall_at_1=recall_at_k(retrieved_ids, gold_chunks, 1),
        recall_at_3=recall_at_k(retrieved_ids, gold_chunks, 3),
        recall_at_5=recall_at_k(retrieved_ids, gold_chunks, 5),
        recall_at_10=recall_at_k(retrieved_ids, gold_chunks, 10),
        recall_at_20=recall_at_k(retrieved_ids, gold_chunks, 20),
        mrr=reciprocal_rank(retrieved_ids, gold_chunks),
        precision_at_5=precision_at_k(retrieved_ids, gold_chunks, 5),
        hit_rate_at_1=hit_rate_at_k(retrieved_ids, gold_chunks, 1),
        hit_rate_at_5=hit_rate_at_k(retrieved_ids, gold_chunks, 5),
        ndcg_at_10=ndcg_at_k(retrieved_ids, gold_chunks, 10),
        document_recall_at_5=recall_at_k(doc_ids, gold_documents, 5),
        document_recall_at_10=recall_at_k(doc_ids, gold_documents, 10),
    )


def _normalize(text: str) -> str:
    return " ".join(text.split())
