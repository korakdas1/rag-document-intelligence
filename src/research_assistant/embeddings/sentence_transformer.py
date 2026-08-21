"""Local sentence-transformers embedding model. Prefixes stay inside this class."""

from __future__ import annotations

from collections.abc import Sequence

from research_assistant.core.errors import EmbeddingError
from research_assistant.core.resource import (
    RESOURCE_EXHAUSTED_CODE,
    RESOURCE_EXHAUSTED_MESSAGE,
    looks_like_resource_exhaustion,
)
from research_assistant.embeddings.device import resolve_device
from research_assistant.embeddings.identity import EmbeddingIdentity
from research_assistant.embeddings.profiles import profile_for


class SentenceTransformerEmbedding:
    def __init__(
        self,
        model_name: str,
        *,
        device: str = "auto",
        normalize: bool | None = None,
        batch_size: int = 32,
        revision: str | None = None,
    ) -> None:
        if batch_size < 1:
            raise EmbeddingError("batch_size must be >= 1", code="invalid_batch_size")
        profile = profile_for(model_name)
        self._model_name = model_name
        self._device = resolve_device(device)
        self._normalize = profile.normalize if normalize is None else normalize
        self._batch_size = batch_size
        self._query_prefix = profile.query_prefix
        self._document_prefix = profile.document_prefix
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError(
                "sentence-transformers is required for local embeddings",
                code="missing_dependency",
            ) from exc
        try:
            kwargs: dict[str, object] = {"device": self._device}
            if revision:
                kwargs["revision"] = revision
            self._model = SentenceTransformer(model_name, **kwargs)
        except Exception as exc:  # noqa: BLE001 — wrap backend load failures
            raise EmbeddingError(
                f"Failed to load embedding model {model_name}: {exc}",
                code="model_load_failed",
            ) from exc
        get_dim = getattr(self._model, "get_embedding_dimension", None)
        if get_dim is None:
            get_dim = self._model.get_sentence_embedding_dimension
        dimension = int(get_dim())
        if profile.expected_dimension and dimension != profile.expected_dimension:
            raise EmbeddingError(
                f"Model {model_name} dimension {dimension} != expected "
                f"{profile.expected_dimension}",
                code="dimension_mismatch",
            )
        resolved_revision = revision or _revision_from_model(self._model) or "unspecified"
        self._identity = EmbeddingIdentity(
            provider="sentence-transformers",
            model_name=model_name,
            revision=resolved_revision,
            dimension=dimension,
            normalize=self._normalize,
            query_prefix=self._query_prefix,
            document_prefix=self._document_prefix,
            metric="cosine",
        )

    @property
    def identity(self) -> EmbeddingIdentity:
        return self._identity

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        prepared = [self._prefixed(text, self._document_prefix, kind="document") for text in texts]
        return self._encode(prepared)

    def embed_query(self, text: str) -> list[float]:
        prepared = self._prefixed(text, self._query_prefix, kind="query")
        return self._encode([prepared])[0]

    def _prefixed(self, text: str, prefix: str, *, kind: str) -> str:
        if not text or not text.strip():
            raise EmbeddingError(
                f"Refusing to embed empty {kind} text",
                code="empty_text",
            )
        if not prefix:
            return text
        return f"{prefix}{text}"

    def _encode(self, texts: list[str]) -> list[list[float]]:
        try:
            vectors = self._model.encode(
                texts,
                batch_size=self._batch_size,
                convert_to_numpy=True,
                normalize_embeddings=self._normalize,
                show_progress_bar=False,
            )
        except Exception as exc:
            if looks_like_resource_exhaustion(exc):
                raise EmbeddingError(
                    RESOURCE_EXHAUSTED_MESSAGE,
                    code=RESOURCE_EXHAUSTED_CODE,
                ) from exc
            raise
        return [row.tolist() for row in vectors]


def _revision_from_model(model: object) -> str | None:
    config = getattr(model, "model_card_data", None)
    base = getattr(config, "base_model_revision", None)
    if isinstance(base, str) and base:
        return base
    inner = getattr(model, "_first_module", lambda: None)()
    auto = getattr(inner, "auto_model", None)
    commit = getattr(getattr(auto, "config", None), "_commit_hash", None)
    if isinstance(commit, str) and commit:
        return commit
    return None
