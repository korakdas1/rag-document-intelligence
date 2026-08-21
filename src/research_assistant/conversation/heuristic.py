"""Heuristic follow-up resolver. Does not answer questions or retrieve."""

from __future__ import annotations

import re
from collections.abc import Sequence

from research_assistant.conversation.detect import (
    has_unresolved_pronoun_referent,
    looks_like_followup,
)
from research_assistant.conversation.entities import (
    entity_phrase,
    expand_ellipsis,
    extract_entities,
    has_explicit_referents,
    substitute_pronouns,
)
from research_assistant.conversation.models import (
    ConversationTurn,
    QueryResolution,
    QueryResolutionDiagnostics,
)
from research_assistant.core.timing import Timer

RESOLVER_ID = "followup.heuristic.v4"
DEFAULT_WINDOW = 4
_DUMMY_IT = re.compile(r"^(is|was|does|did)\s+it\b", re.IGNORECASE)


class HeuristicQueryResolver:
    """Rewrite ambiguous follow-ups into a standalone retrieval query."""

    def __init__(self, *, window: int = DEFAULT_WINDOW) -> None:
        if window < 1:
            raise ValueError("conversation window must be >= 1")
        self._window = window

    @property
    def resolver_id(self) -> str:
        return RESOLVER_ID

    def resolve(
        self,
        question: str,
        history: Sequence[ConversationTurn] | None = None,
    ) -> QueryResolution:
        original = (question or "").strip()
        bounded = _bound(history, self._window)
        with Timer("query_resolve") as timer:
            if not bounded and has_unresolved_pronoun_referent(original):
                rewritten, ambiguous, method = original, True, "unresolved_no_history"
                followup = False
                entities = ()
            else:
                followup = looks_like_followup(original) and bool(bounded)
                entities = extract_entities(bounded) if followup else ()
                rewritten, ambiguous, method = _rewrite(
                    original,
                    followup=followup,
                    entities=entities,
                    history=bounded,
                )
        elapsed = timer.seconds * 1000
        applied = rewritten != original
        diagnostics = QueryResolutionDiagnostics(
            original_question=original,
            retrieval_query=rewritten,
            rewrite_applied=applied,
            followup_detected=followup,
            ambiguous=ambiguous,
            history_turns_used=len(bounded) if followup else 0,
            resolver_id=self.resolver_id,
            method=method,
            entities=entities,
            elapsed_ms=elapsed,
        )
        return QueryResolution(
            original_question=original,
            retrieval_query=rewritten,
            rewrite_applied=applied,
            followup_detected=followup,
            ambiguous=ambiguous,
            diagnostics=diagnostics,
        )


def _bound(
    history: Sequence[ConversationTurn] | None, window: int
) -> tuple[ConversationTurn, ...]:
    if not history:
        return ()
    items = tuple(history)[-window:]
    numbered: list[ConversationTurn] = []
    start = max(0, len(tuple(history)) - len(items))
    for offset, turn in enumerate(items):
        numbered.append(
            ConversationTurn(
                question=turn.question.strip(),
                answer=turn.answer.strip(),
                grounding_status=turn.grounding_status,
                sequence=turn.sequence or start + offset + 1,
            )
        )
    return tuple(numbered)


def _rewrite(
    question: str,
    *,
    followup: bool,
    entities: tuple[str, ...],
    history: Sequence[ConversationTurn],
) -> tuple[str, bool, str]:
    if not followup:
        return question, False, "passthrough"
    previous = history[-1].question if history else ""
    expanded = expand_ellipsis(question, entities=entities, previous_question=previous)
    if expanded:
        phrase = entity_phrase(entities)
        substituted = substitute_pronouns(expanded, phrase) if phrase else expanded
        return _ensure_question(substituted), False, "ellipsis"
    if has_explicit_referents(question, entities):
        return question, False, "explicit_entities"
    phrase = entity_phrase(entities)
    if phrase:
        substituted = substitute_pronouns(question, phrase)
        if substituted != question:
            return _ensure_question(substituted), False, "pronoun_substitution"
        lowered = question.lower()
        if _DUMMY_IT.match(question):
            return (
                _ensure_question(f"{question.rstrip('?')} for {phrase}?"),
                False,
                "topic_expansion",
            )
        if "sure" in lowered:
            return (
                f"Does the indexed document support claims about {phrase}?",
                False,
                "topic_expansion",
            )
        return _ensure_question(f"{question.rstrip('?')} regarding {phrase}?"), False, "topic_expansion"
    if previous:
        return (
            _ensure_question(f"{question.rstrip('?')} regarding '{previous}'?"),
            True,
            "previous_question",
        )
    return question, True, "unresolved"


def _ensure_question(text: str) -> str:
    stripped = text.strip()
    if not stripped.endswith("?"):
        return stripped + "?"
    return stripped
