"""Okapi BM25 over in-memory tokenized chunks. Scores are not probabilities."""

from __future__ import annotations

import math
from collections import Counter

DEFAULT_BM25_K1 = 1.2
DEFAULT_BM25_B = 0.75


class BM25Index:
    """Lucene-style IDF BM25. ``k1`` and ``b`` are development defaults."""

    def __init__(
        self,
        documents: list[tuple[str, tuple[str, ...]]],
        *,
        k1: float = DEFAULT_BM25_K1,
        b: float = DEFAULT_BM25_B,
    ) -> None:
        if k1 < 0:
            raise ValueError("bm25 k1 must be >= 0")
        if not 0 <= b <= 1:
            raise ValueError("bm25 b must be in [0, 1]")
        self.k1 = k1
        self.b = b
        self.doc_ids = [doc_id for doc_id, _ in documents]
        self._index = {doc_id: i for i, doc_id in enumerate(self.doc_ids)}
        self.tf = [Counter(tokens) for _, tokens in documents]
        self.doc_len = [sum(counter.values()) for counter in self.tf]
        self.n_docs = len(documents)
        total_len = sum(self.doc_len)
        self.avgdl = (total_len / self.n_docs) if self.n_docs else 0.0
        df: Counter[str] = Counter()
        for counter in self.tf:
            df.update(counter.keys())
        self.idf = {
            term: math.log(1.0 + (self.n_docs - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def score(self, query_tokens: tuple[str, ...], doc_id: str) -> float:
        position = self._index.get(doc_id)
        if position is None:
            return 0.0
        length = self.doc_len[position]
        if length == 0 or self.avgdl == 0:
            return 0.0
        denom_norm = self.k1 * (1.0 - self.b + self.b * length / self.avgdl)
        tf_map = self.tf[position]
        score = 0.0
        for term, query_tf in Counter(query_tokens).items():
            term_tf = tf_map.get(term, 0)
            if term_tf == 0:
                continue
            idf = self.idf.get(term, 0.0)
            score += query_tf * idf * (term_tf * (self.k1 + 1.0)) / (term_tf + denom_norm)
        return score

    def rank(
        self,
        query_tokens: tuple[str, ...],
        *,
        candidate_ids: list[str] | None = None,
        top_k: int,
    ) -> list[tuple[str, float]]:
        ids = candidate_ids if candidate_ids is not None else self.doc_ids
        scored = [
            (doc_id, self.score(query_tokens, doc_id))
            for doc_id in ids
            if doc_id in self._index
        ]
        scored = [item for item in scored if item[1] > 0.0]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_k]
