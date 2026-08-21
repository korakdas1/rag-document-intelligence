"""Query-preserving pair truncation for cross-encoder input limits.

Uses the same ~4 characters/token estimate as chunking. This is not the
model tokenizer; sentence-transformers may still clip remaining overflow.
"""

from __future__ import annotations

from research_assistant.chunking.identity import approx_token_count

_SPECIAL_TOKEN_RESERVE = 8
_MIN_PASSAGE_TOKENS = 16


def prepare_rerank_pair(
    query: str,
    passage: str,
    max_length: int,
) -> tuple[str, str, bool]:
    """Return (query, passage, truncated) that fit an approximate token budget.

    The query is kept whole unless it alone exceeds ``max_length`` minus a
    small reserve. The passage is truncated from the end. ``max_length <= 0``
    disables truncation.
    """
    if max_length <= 0:
        return query, passage, False
    query_tokens = approx_token_count(len(query))
    query_budget = min(query_tokens, max(max_length - _SPECIAL_TOKEN_RESERVE - _MIN_PASSAGE_TOKENS, 1))
    query_chars = query_budget * 4
    out_query = query
    query_cut = False
    if len(query) > query_chars:
        out_query = query[:query_chars]
        query_cut = True
    remaining_tokens = max(
        max_length - approx_token_count(len(out_query)) - _SPECIAL_TOKEN_RESERVE,
        _MIN_PASSAGE_TOKENS,
    )
    passage_chars = remaining_tokens * 4
    if len(passage) <= passage_chars:
        return out_query, passage, query_cut
    return out_query, passage[:passage_chars], True
