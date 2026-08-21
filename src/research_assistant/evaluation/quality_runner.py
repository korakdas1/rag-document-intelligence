"""Qualitybench runner. Calls production retrieval/generation; does not change them."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from research_assistant.app import Application
from research_assistant.conversation.heuristic import HeuristicQueryResolver
from research_assistant.conversation.models import ConversationTurn
from research_assistant.core.errors import EvaluationError, GenerationError
from research_assistant.core.types import RetrievalMode
from research_assistant.evaluation.gold import contribution_label, resolve_gold
from research_assistant.evaluation.identity import git_commit, make_run_id, utc_stamp
from research_assistant.evaluation.metrics import recall_at_k, token_f1
from research_assistant.evaluation.models import EvalStage, EvaluationDataset, EvaluationExample, Split
from research_assistant.evaluation.quality_metrics import (
    conflict_reported,
    first_gold_rank,
    forbidden_hit,
    gold_present,
    key_fact_hits,
    key_fact_recall,
    product_status,
    quality_aggregates,
    slot_results,
    unverified_reason,
)
from research_assistant.evaluation.quality_taxonomy import classify_quality
from research_assistant.evaluation.runner import _citation_support, _ids, _score_list
from research_assistant.evaluation.semantic_support import (
    classify_cited_support,
    repair_drift,
)
from research_assistant.generation import prompt as prompt_mod
from research_assistant.generation.citations import PARSER_VERSION
from research_assistant.retrieval.filters import RetrievalFilter


class QualityEvaluationRunner:
    def __init__(
        self,
        app: Application,
        dataset: EvaluationDataset,
        *,
        chunker_id: str,
    ) -> None:
        self._app = app
        self._dataset = dataset
        self._chunker_id = chunker_id
        self._resolver = HeuristicQueryResolver(window=app.settings.conversation_window)

    def run(
        self,
        *,
        stage: str = EvalStage.FULL.value,
        mode: str = RetrievalMode.HYBRID.value,
        split: str | None = Split.TEST.value,
        candidate_k: int | None = None,
        rerank_top_k: int | None = None,
        max_context_tokens: int | None = None,
        rerank_enabled: bool | None = None,
        repeat: int = 1,
        tag: str | None = None,
        example_ids: Sequence[str] | None = None,
        output_dir: Path | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            resolved_stage = EvalStage(stage)
        except ValueError as exc:
            raise EvaluationError(f"Unknown evaluation stage {stage!r}", code="invalid_stage") from exc
        if repeat < 1:
            raise EvaluationError("repeat must be >= 1", code="invalid_repeat")
        examples = self._dataset.filter_split(split)
        if tag:
            examples = tuple(item for item in examples if tag in item.tags)
        if example_ids:
            wanted = set(example_ids)
            examples = tuple(item for item in examples if item.example_id in wanted)
            missing = wanted - {item.example_id for item in examples}
            if missing:
                raise EvaluationError(
                    f"Unknown example_ids: {sorted(missing)}",
                    code="unknown_example_ids",
                )
        if not examples:
            raise EvaluationError("No examples in the requested split", code="empty_split")
        settings = self._app.settings
        pool_k = candidate_k if candidate_k is not None else settings.rerank_candidate_k
        use_rerank = settings.rerank_enabled if rerank_enabled is None else rerank_enabled
        config = {
            "dataset_id": self._dataset.dataset_id,
            "dataset_version": self._dataset.version,
            "family": "qualitybench",
            "stage": resolved_stage.value,
            "mode": mode,
            "split": split,
            "chunker_id": self._chunker_id,
            "candidate_k": pool_k,
            "dense_candidate_k": settings.dense_candidate_k,
            "lexical_candidate_k": settings.lexical_candidate_k,
            "rrf_k": settings.rrf_k,
            "rerank_enabled": use_rerank,
            "reranker_model": settings.reranker_model_name,
            "rerank_top_k": rerank_top_k if rerank_top_k is not None else settings.rerank_top_k,
            "max_context_tokens": max_context_tokens
            if max_context_tokens is not None
            else settings.max_context_tokens,
            "embedding_model": settings.embedding_model_name,
            "llm_model": settings.llm_model_name,
            "llm_provider": settings.llm_provider,
            "llm_temperature": settings.llm_temperature,
            "prompt_id": prompt_mod.PROMPT_VERSION,
            "parser_id": PARSER_VERSION,
            "resolver_id": self._resolver.resolver_id,
            "llm_citation_repair": settings.llm_citation_repair,
            "llm_keep_alive": settings.llm_keep_alive,
            "llm_repair_model": settings.llm_repair_model_name,
            "repeat": repeat,
            "tag": tag,
            "example_ids": list(example_ids) if example_ids else None,
        }
        stamp = utc_stamp()
        rid = run_id or make_run_id(config, stamp=stamp)
        rows: list[dict[str, Any]] = []
        for example in examples:
            for index in range(repeat):
                rows.append(
                    self._evaluate_one(
                        example,
                        stage=resolved_stage,
                        mode=mode,
                        pool_k=pool_k,
                        rerank_top_k=int(config["rerank_top_k"]),
                        max_context_tokens=int(config["max_context_tokens"]),
                        rerank_enabled=use_rerank,
                        run_index=index,
                    )
                )
        report = {
            "run_id": rid,
            "date": stamp,
            "git_commit": git_commit(),
            "config": config,
            "identities": self._identities(),
            "metrics": quality_aggregates(rows, examples),
            "examples": rows,
        }
        extra = _slice_reports(rows, examples)
        report["metrics"].update(extra)
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
        rerank_enabled: bool,
        run_index: int,
    ) -> dict[str, Any]:
        gold = resolve_gold(example, self._app.store, self._chunker_id)
        history = _history(example)
        resolution = self._resolver.resolve(example.question, history or None)
        retrieval_query = resolution.retrieval_query
        rewrite_error = _rewrite_error(example, retrieval_query)
        filters = None
        if example.selected_filenames:
            filters = RetrievalFilter(filenames=example.selected_filenames)
        dense = self._app.hybrid.search(
            retrieval_query,
            chunker_id=self._chunker_id,
            mode=RetrievalMode.DENSE.value,
            top_k=pool_k,
            filters=filters,
        )
        lexical = self._app.hybrid.search(
            retrieval_query,
            chunker_id=self._chunker_id,
            mode=RetrievalMode.LEXICAL.value,
            top_k=pool_k,
            filters=filters,
        )
        primary = self._app.hybrid.search(
            retrieval_query,
            chunker_id=self._chunker_id,
            mode=mode,
            top_k=pool_k,
            filters=filters,
        )
        dense_ids = _ids(dense.hits)
        lexical_ids = _ids(lexical.hits)
        primary_ids = _ids(primary.hits)
        row: dict[str, Any] = {
            "example_id": example.example_id,
            "question": example.question,
            "resolved_query": retrieval_query,
            "original_question": resolution.original_question,
            "rewrite_applied": resolution.rewrite_applied,
            "followup_detected": resolution.followup_detected,
            "ambiguous": resolution.ambiguous,
            "resolver_method": resolution.diagnostics.method,
            "rewrite_error": rewrite_error,
            "resolver_entities": list(resolution.diagnostics.entities),
            "split": example.split.value,
            "category": example.category,
            "slice": example.slice_name,
            "answerable": example.answerable,
            "expected_chunk_ids": sorted(gold.chunk_ids),
            "expected_filenames": list(example.relevant_filenames),
            "selected_filenames": list(example.selected_filenames),
            "dense_ids": dense_ids,
            "lexical_ids": lexical_ids,
            "hybrid_ids": primary_ids,
            "contribution": contribution_label(gold.chunk_ids, dense_ids, lexical_ids),
            "gold_in_dense": gold_present(dense_ids, gold.chunk_ids),
            "gold_in_lexical": gold_present(lexical_ids, gold.chunk_ids),
            "gold_in_hybrid": gold_present(primary_ids, gold.chunk_ids),
            "gold_rank_dense": first_gold_rank(dense_ids, gold.chunk_ids),
            "gold_rank_lexical": first_gold_rank(lexical_ids, gold.chunk_ids),
            "gold_rank_hybrid": first_gold_rank(primary_ids, gold.chunk_ids),
            "retrieval_scores": _score_list(
                primary_ids, gold.chunk_ids, primary.hits, gold.document_ids
            ).to_dict(),
            "timings_ms": {
                "dense_ms": dense.diagnostics.total_ms,
                "lexical_ms": lexical.diagnostics.total_ms,
                "fusion_ms": primary.diagnostics.fusion_ms,
                "retrieval_ms": primary.diagnostics.total_ms,
                "resolve_ms": resolution.diagnostics.elapsed_ms,
            },
            "candidate_recall": recall_at_k(primary_ids, gold.chunk_ids, pool_k),
            "run_index": run_index,
        }
        if stage is EvalStage.RETRIEVAL:
            primary_fail, secondary = classify_quality(example, row)
            row["primary_failure"] = primary_fail
            row["secondary_failures"] = secondary
            row["product_status"] = None
            row["timings_ms"]["total_ms"] = row["timings_ms"]["retrieval_ms"]
            return row

        evidence = self._app.evidence.collect(
            retrieval_query,
            chunker_id=self._chunker_id,
            mode=mode,
            filters=filters,
            candidate_k=pool_k,
            rerank_top_k=rerank_top_k,
            max_context_tokens=max_context_tokens,
            rerank_enabled=rerank_enabled,
        )
        rerank_ids = _ids(evidence.rerank.hits)
        context_ids = [item.source.chunk_id for item in evidence.context.items]
        row["rerank_ids"] = rerank_ids
        row["rerank_scores"] = _score_list(
            rerank_ids, gold.chunk_ids, evidence.rerank.hits, gold.document_ids
        ).to_dict()
        row["context_chunk_ids"] = context_ids
        row["context_citation_ids"] = [item.citation_id for item in evidence.context.items]
        row["context_blocks"] = [
            {
                "citation_id": item.citation_id,
                "chunk_id": item.source.chunk_id,
                "text": item.text,
            }
            for item in evidence.context.items
        ]
        row["gold_in_rerank"] = gold_present(rerank_ids, gold.chunk_ids)
        row["gold_rank_rerank"] = first_gold_rank(rerank_ids, gold.chunk_ids)
        row["gold_in_context"] = bool(gold.chunk_ids & set(context_ids)) if gold.chunk_ids else None
        row["gold_rank_context"] = first_gold_rank(context_ids, gold.chunk_ids)
        denom = max(len(context_ids), 1)
        row["context_evidence_recall"] = recall_at_k(context_ids, gold.chunk_ids, denom)
        row["timings_ms"]["rerank_ms"] = evidence.rerank.diagnostics.inference_ms
        row["timings_ms"]["retrieval_ms"] = evidence.search.diagnostics.total_ms
        if stage in {EvalStage.RERANK, EvalStage.CONTEXT}:
            primary_fail, secondary = classify_quality(example, row)
            row["primary_failure"] = primary_fail
            row["secondary_failures"] = secondary
            row["product_status"] = None
            row["timings_ms"]["total_ms"] = (
                row["timings_ms"]["retrieval_ms"] + row["timings_ms"]["rerank_ms"]
            )
            return row

        try:
            answer = self._app.generation.generate(
                retrieval_query,
                evidence.context,
                unresolved_referent=resolution.diagnostics.method == "unresolved_no_history",
            )
            cited = [item.source.chunk_id for item in answer.citations]
            row["answer_text"] = answer.answer_text
            row["raw_response"] = answer.raw_response
            row["validation_status"] = answer.validation_status.value
            row["insufficient_evidence"] = answer.insufficient_evidence
            row["cited_chunk_ids"] = cited
            row["cited_citation_ids"] = [item.citation_id for item in answer.citations]
            row["invalid_citation_ids"] = list(answer.invalid_citation_ids)
            row["technical_error"] = None
            row["timings_ms"]["generation_ms"] = answer.diagnostics.generation_ms
            row["timings_ms"]["first_pass_generation_ms"] = (
                answer.diagnostics.first_pass_generation_ms
            )
            row["timings_ms"]["repair_ms"] = answer.diagnostics.repair_ms
            row["repair_attempts"] = answer.diagnostics.repair_attempts
            row["unresolved_referent_short_circuit"] = (
                answer.diagnostics.unresolved_referent_short_circuit
            )
            row["first_pass_validation_status"] = (
                answer.diagnostics.first_pass_validation_status
            )
            row["first_pass_answer_text"] = answer.diagnostics.first_pass_answer_text
            row["claim_sources_field"] = [
                {"claim": claim, "source_ids": list(ids)}
                for claim, ids in answer.diagnostics.claim_sources
            ]
            row["sources_disagree_field"] = answer.diagnostics.sources_disagree
            row["llm_calls"] = (
                0
                if answer.diagnostics.unresolved_referent_short_circuit
                or answer.diagnostics.empty_context_short_circuit
                else 1
                + int(answer.diagnostics.repair_attempts)
                + int(answer.diagnostics.format_repair_attempted)
            )
        except GenerationError as exc:
            row["answer_text"] = ""
            row["raw_response"] = ""
            row["validation_status"] = None
            row["insufficient_evidence"] = None
            row["cited_chunk_ids"] = []
            row["cited_citation_ids"] = []
            row["invalid_citation_ids"] = []
            row["technical_error"] = f"{exc.code}: {exc.message}"
            row["timings_ms"]["generation_ms"] = 0.0
            row["timings_ms"]["first_pass_generation_ms"] = 0.0
            row["timings_ms"]["repair_ms"] = 0.0
            row["repair_attempts"] = 0
            row["unresolved_referent_short_circuit"] = False
            row["first_pass_validation_status"] = ""
            row["first_pass_answer_text"] = ""
            row["claim_sources_field"] = []
            row["sources_disagree_field"] = None
            row["llm_calls"] = 0
        row["key_fact_hits"] = key_fact_hits(row.get("answer_text") or "", example.key_facts)
        row["key_fact_recall"] = key_fact_recall(row.get("answer_text") or "", example.key_facts)
        row["forbidden_hit"] = forbidden_hit(row.get("answer_text") or "", example.forbidden_facts)
        row["lexical_citation_support"] = _citation_support(
            example, tuple(row.get("cited_chunk_ids") or ()), self._app.store
        )
        row["conflict_reported"] = conflict_reported(row.get("answer_text") or "")
        row["claim_slots"] = slot_results(
            row.get("answer_text") or "",
            example,
            tuple(row.get("cited_chunk_ids") or ()),
            self._app.store,
        )
        row["reference_token_f1"] = token_f1(row.get("answer_text") or "", example.reference_answer or "")
        row["product_status"] = product_status(
            row.get("validation_status"),
            technical=bool(row.get("technical_error")),
        )
        row["semantically_supported_grounded"] = (
            row.get("product_status") == "GROUNDED"
            and (row.get("lexical_citation_support") or 0) > 0
        )
        row["product_grounded_unsupported"] = (
            row.get("product_status") == "GROUNDED"
            and row.get("lexical_citation_support") == 0.0
        )
        cited_ids = list(row.get("cited_citation_ids") or [])
        blocks = {
            str(item.get("citation_id")): str(item.get("text") or "")
            for item in row.get("context_blocks") or []
        }
        cited_texts = [blocks[cid] for cid in cited_ids if cid in blocks]
        row["cited_passages"] = [
            {"citation_id": cid, "text": blocks.get(cid, "")} for cid in cited_ids
        ]
        row["support_class"] = classify_cited_support(
            product_status=row.get("product_status"),
            gold_passages=[item.text for item in example.gold_passages],
            cited_texts=cited_texts,
            has_valid_citation=bool(cited_ids)
            and row.get("validation_status") == "valid",
        )
        if row.get("repair_attempts"):
            row["repair_drift"] = repair_drift(
                str(row.get("first_pass_answer_text") or ""),
                str(row.get("answer_text") or ""),
            )
        else:
            row["repair_drift"] = {"changed": False, "kinds": []}
        row["unverified_reason"] = unverified_reason(
            validation_status=row.get("validation_status"),
            key_fact_recall_value=row.get("key_fact_recall"),
        )
        row["timings_ms"]["total_ms"] = (
            row["timings_ms"]["retrieval_ms"]
            + row["timings_ms"].get("rerank_ms", 0.0)
            + row["timings_ms"].get("generation_ms", 0.0)
        )
        primary_fail, secondary = classify_quality(example, row)
        row["primary_failure"] = primary_fail
        row["secondary_failures"] = secondary
        return row

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
        payload["resolver_id"] = self._resolver.resolver_id
        return payload


def write_citation_review_csv(report: dict[str, Any], path: Path) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for item in report.get("examples") or []:
        claims_n = max(len(item.get("cited_citation_ids") or [None]), 1)
        answer = str(item.get("answer_text") or "")
        citations = item.get("cited_citation_ids") or []
        if not citations:
            rows.append(
                {
                    "question_id": item.get("example_id") or "",
                    "claim_id": "",
                    "claim_text": answer[:240],
                    "citation_id": "",
                    "source_locator": ",".join(item.get("expected_filenames") or []),
                    "supported": "unclear",
                    "notes": item.get("product_status") or "",
                }
            )
            continue
        for citation_id in citations:
            rows.append(
                {
                    "question_id": item.get("example_id") or "",
                    "claim_id": "",
                    "claim_text": answer[:240],
                    "citation_id": str(citation_id),
                    "source_locator": ",".join(item.get("expected_filenames") or []),
                    "supported": "unclear",
                    "notes": "fill during human review",
                }
            )
        _ = claims_n
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "question_id",
                "claim_id",
                "claim_text",
                "citation_id",
                "source_locator",
                "supported",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _history(example: EvaluationExample) -> tuple[ConversationTurn, ...]:
    turns: list[ConversationTurn] = []
    for index, item in enumerate(example.history, start=1):
        turns.append(
            ConversationTurn(
                question=str(item.get("question") or ""),
                answer=str(item.get("answer") or ""),
                grounding_status=str(item.get("grounding_status") or ""),
                sequence=index,
            )
        )
    return tuple(turns)


def _rewrite_error(example: EvaluationExample, retrieval_query: str) -> bool:
    lowered = retrieval_query.lower()
    if example.expected_resolved_contains:
        if any(token.lower() not in lowered for token in example.expected_resolved_contains):
            return True
    if example.expected_resolved_must_not:
        if any(token.lower() in lowered for token in example.expected_resolved_must_not):
            return True
    return False


def _slice_reports(
    rows: list[dict[str, Any]],
    examples: tuple[EvaluationExample, ...],
) -> dict[str, Any]:
    by_slice: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_slice.setdefault(str(row.get("slice") or "unspecified"), []).append(row)
    return {
        "by_slice": {
            name: quality_aggregates(items, examples) for name, items in sorted(by_slice.items())
        },
        "paraphrase_stability": _paraphrase_stability(rows, examples),
    }


def _paraphrase_stability(
    rows: list[dict[str, Any]],
    examples: tuple[EvaluationExample, ...],
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    by_id = {item.example_id: item for item in examples}
    for row in rows:
        group = by_id[row["example_id"]].paraphrase_group
        if group:
            groups.setdefault(group, []).append(row)
    out: dict[str, Any] = {}
    for name, items in groups.items():
        statuses = {item.get("product_status") for item in items}
        facts = {item.get("key_fact_recall") for item in items}
        out[name] = {
            "n": len(items),
            "distinct_product_status": len(statuses),
            "status_set": sorted(str(item) for item in statuses),
            "distinct_key_fact_recall": len(facts),
            "stable": len(statuses) == 1 and len(facts) == 1,
        }
    return out
