"""Query resolver protocol. Produces a retrieval query, never an answer."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from research_assistant.conversation.models import ConversationTurn, QueryResolution


class QueryResolver(Protocol):
    @property
    def resolver_id(self) -> str: ...

    def resolve(
        self,
        question: str,
        history: Sequence[ConversationTurn] | None = None,
    ) -> QueryResolution: ...
