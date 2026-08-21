"""Local sentence-transformers CrossEncoder. Scores are ranking logits, not probabilities."""

from __future__ import annotations

from collections.abc import Sequence

from research_assistant.core.errors import RerankError
from research_assistant.core.timing import Timer
from research_assistant.embeddings.device import resolve_device
from research_assistant.reranking.identity import RerankerIdentity
from research_assistant.reranking.models import RerankResult
from research_assistant.reranking.ranking import empty_result, ranked_result, require_query, require_top_k
from research_assistant.reranking.truncate import prepare_rerank_pair
from research_assistant.retrieval.models import RetrievalHit


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str,
        *,
        device: str = "auto",
        batch_size: int = 8,
        max_length: int = 512,
        revision: str | None = None,
    ) -> None:
        if batch_size < 1:
            raise RerankError("batch_size must be >= 1", code="invalid_batch_size")
        if max_length < 1:
            raise RerankError("max_length must be >= 1", code="invalid_max_length")
        self._device = resolve_device(device)
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RerankError(
                "sentence-transformers is required for cross-encoder reranking",
                code="missing_dependency",
            ) from exc
        try:
            kwargs: dict[str, object] = {
                "device": self._device,
                "max_length": max_length,
            }
            if revision:
                kwargs["revision"] = revision
            self._model = CrossEncoder(model_name, **kwargs)
        except RerankError:
            raise
        except Exception as exc:  # noqa: BLE001 — wrap backend load failures
            raise RerankError(
                f"Failed to load reranker model {model_name}: {exc}",
                code="model_unavailable",
            ) from exc
        resolved_revision = revision or _revision_from_model(self._model) or "unspecified"
        self._identity = RerankerIdentity(
            provider="sentence-transformers-cross-encoder",
            model_name=model_name,
            revision=resolved_revision,
            max_length=max_length,
            batch_size=batch_size,
            scoring="logit",
            device=self._device,
        )

    @property
    def identity(self) -> RerankerIdentity:
        return self._identity

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalHit],
        top_k: int,
    ) -> RerankResult:
        query = require_query(query)
        top_k = require_top_k(top_k)
        if not candidates:
            return empty_result(query, self._identity, enabled=True)
        pairs: list[tuple[str, str]] = []
        truncated_count = 0
        max_length = self._identity.max_length
        for hit in candidates:
            pair_query, pair_passage, truncated = prepare_rerank_pair(
                query, hit.text, max_length
            )
            if truncated:
                truncated_count += 1
            pairs.append((pair_query, pair_passage))
        try:
            with Timer("cross_encoder_predict") as timer:
                raw_scores = self._model.predict(
                    pairs,
                    batch_size=self._identity.batch_size,
                    show_progress_bar=False,
                )
        except Exception as exc:  # noqa: BLE001 — wrap inference failures
            raise RerankError(
                f"Cross-encoder inference failed: {exc}",
                code="inference_failed",
            ) from exc
        scores = [float(score) for score in raw_scores]
        if len(scores) != len(candidates):
            raise RerankError(
                "Cross-encoder returned a different number of scores than candidates",
                code="inference_failed",
            )
        scored = list(zip(candidates, scores, strict=True))
        return ranked_result(
            query,
            self._identity,
            scored,
            top_k=top_k,
            truncated_count=truncated_count,
            inference_ms=timer.seconds * 1000,
        )


def _revision_from_model(model: object) -> str | None:
    tokenizer = getattr(model, "tokenizer", None)
    name_or_path = getattr(tokenizer, "name_or_path", None)
    if isinstance(name_or_path, str) and name_or_path:
        return name_or_path
    config = getattr(model, "config", None) or getattr(
        getattr(model, "model", None), "config", None
    )
    name = getattr(config, "_name_or_path", None)
    if isinstance(name, str) and name:
        return name
    return None
