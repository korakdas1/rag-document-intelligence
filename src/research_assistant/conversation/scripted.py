"""Deterministic query-resolver test double. Never calls an LLM."""

from __future__ import annotations

from collections.abc import Sequence

from research_assistant.conversation.models import (
    ConversationTurn,
    QueryResolution,
    QueryResolutionDiagnostics,
)

RESOLVER_ID = "followup.scripted.v1"


class ScriptedQueryResolver:
    """Returns a predetermined retrieval query, or the original question."""

    def __init__(
        self,
        retrieval_query: str | None = None,
        *,
        rewrite_applied: bool | None = None,
        followup_detected: bool = False,
        ambiguous: bool = False,
        method: str = "scripted",
    ) -> None:
        self._retrieval_query = retrieval_query
        self._rewrite_applied = rewrite_applied
        self._followup_detected = followup_detected
        self._ambiguous = ambiguous
        self._method = method
        self.questions: list[str] = []
        self.histories: list[tuple[ConversationTurn, ...]] = []

    @property
    def resolver_id(self) -> str:
        return RESOLVER_ID

    def resolve(
        self,
        question: str,
        history: Sequence[ConversationTurn] | None = None,
    ) -> QueryResolution:
        original = (question or "").strip()
        bounded = tuple(history or ())
        self.questions.append(original)
        self.histories.append(bounded)
        rewritten = (self._retrieval_query or original).strip()
        applied = (
            self._rewrite_applied
            if self._rewrite_applied is not None
            else rewritten != original
        )
        diagnostics = QueryResolutionDiagnostics(
            original_question=original,
            retrieval_query=rewritten,
            rewrite_applied=applied,
            followup_detected=self._followup_detected,
            ambiguous=self._ambiguous,
            history_turns_used=len(bounded),
            resolver_id=self.resolver_id,
            method=self._method,
            entities=(),
            elapsed_ms=0.0,
        )
        return QueryResolution(
            original_question=original,
            retrieval_query=rewritten,
            rewrite_applied=applied,
            followup_detected=self._followup_detected,
            ambiguous=self._ambiguous,
            diagnostics=diagnostics,
        )
