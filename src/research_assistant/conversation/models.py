"""Runtime conversation types. Not persisted. History is never evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConversationTurn:
    question: str
    answer: str
    grounding_status: str = ""
    sequence: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "grounding_status": self.grounding_status,
            "sequence": self.sequence,
        }


@dataclass(frozen=True)
class QueryResolutionDiagnostics:
    original_question: str
    retrieval_query: str
    rewrite_applied: bool
    followup_detected: bool
    ambiguous: bool
    history_turns_used: int
    resolver_id: str
    method: str
    entities: tuple[str, ...]
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_question": self.original_question,
            "retrieval_query": self.retrieval_query,
            "rewrite_applied": self.rewrite_applied,
            "followup_detected": self.followup_detected,
            "ambiguous": self.ambiguous,
            "history_turns_used": self.history_turns_used,
            "resolver_id": self.resolver_id,
            "method": self.method,
            "entities": list(self.entities),
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


@dataclass(frozen=True)
class QueryResolution:
    original_question: str
    retrieval_query: str
    rewrite_applied: bool
    followup_detected: bool
    ambiguous: bool
    diagnostics: QueryResolutionDiagnostics

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_question": self.original_question,
            "retrieval_query": self.retrieval_query,
            "rewrite_applied": self.rewrite_applied,
            "followup_detected": self.followup_detected,
            "ambiguous": self.ambiguous,
            "diagnostics": self.diagnostics.to_dict(),
        }
