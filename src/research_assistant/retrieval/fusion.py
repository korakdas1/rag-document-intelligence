"""Rank fusion. Do not add raw cosine and BM25 scores."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

DEFAULT_RRF_K = 60


@dataclass(frozen=True)
class RankedItem:
    chunk_id: str
    rank: int
    score: float
    retriever: str


@dataclass(frozen=True)
class FusedItem:
    chunk_id: str
    fused_score: float
    ranks: dict[str, int]
    scores: dict[str, float]


class FusionStrategy(Protocol):
    def fuse(self, lists: Sequence[Sequence[RankedItem]]) -> list[FusedItem]: ...


class ReciprocalRankFusion:
    """RRF: sum 1/(k + rank) over retrievers. Rank is 1-based.

    ``k=60`` is a common development default, not an optimum.
    Ties: higher fused score, then best (lowest) component rank, then chunk_id.
    """

    def __init__(self, k: int = DEFAULT_RRF_K) -> None:
        if k < 0:
            raise ValueError("RRF k must be >= 0")
        self.k = k

    def fuse(self, lists: Sequence[Sequence[RankedItem]]) -> list[FusedItem]:
        ranks: dict[str, dict[str, int]] = {}
        scores: dict[str, dict[str, float]] = {}
        fused: dict[str, float] = {}
        for ranked in lists:
            for item in ranked:
                fused[item.chunk_id] = fused.get(item.chunk_id, 0.0) + 1.0 / (
                    self.k + item.rank
                )
                ranks.setdefault(item.chunk_id, {})[item.retriever] = item.rank
                scores.setdefault(item.chunk_id, {})[item.retriever] = item.score
        items = [
            FusedItem(
                chunk_id=chunk_id,
                fused_score=score,
                ranks=ranks[chunk_id],
                scores=scores[chunk_id],
            )
            for chunk_id, score in fused.items()
        ]
        items.sort(
            key=lambda item: (
                -item.fused_score,
                min(item.ranks.values()),
                item.chunk_id,
            )
        )
        return items
