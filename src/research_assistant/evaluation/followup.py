"""Follow-up resolver scoring. Deterministic; no LLM."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research_assistant.conversation.heuristic import HeuristicQueryResolver
from research_assistant.conversation.models import ConversationTurn, QueryResolution
from research_assistant.conversation.protocol import QueryResolver


@dataclass(frozen=True)
class FollowupExample:
    example_id: str
    category: str
    question: str
    history: tuple[ConversationTurn, ...]
    rewrite_required: bool
    must_contain: tuple[str, ...]
    must_contain_any: tuple[str, ...]
    must_not_contain: tuple[str, ...]
    must_equal: str | None
    expect_followup: bool | None
    gold_filenames: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FollowupExample:
        history = tuple(
            ConversationTurn(
                question=str(item.get("question") or ""),
                answer=str(item.get("answer") or ""),
                grounding_status=str(item.get("grounding_status") or ""),
                sequence=index + 1,
            )
            for index, item in enumerate(data.get("history") or [])
        )
        return cls(
            example_id=str(data["example_id"]),
            category=str(data.get("category") or "unspecified"),
            question=str(data["question"]),
            history=history,
            rewrite_required=bool(data.get("rewrite_required", False)),
            must_contain=tuple(str(item) for item in data.get("must_contain") or ()),
            must_contain_any=tuple(
                str(item) for item in data.get("must_contain_any") or ()
            ),
            must_not_contain=tuple(
                str(item) for item in data.get("must_not_contain") or ()
            ),
            must_equal=data.get("must_equal"),
            expect_followup=data.get("expect_followup"),
            gold_filenames=tuple(str(item) for item in data.get("gold_filenames") or ()),
        )


def load_followup_dataset(path: Path | str) -> tuple[FollowupExample, ...]:
    target = Path(path)
    examples: list[FollowupExample] = []
    with target.open(encoding="utf-8") as handle:
        for raw in handle:
            text = raw.strip()
            if not text or text.startswith("#"):
                continue
            examples.append(FollowupExample.from_dict(json.loads(text)))
    return tuple(examples)


def score_resolution(example: FollowupExample, resolution: QueryResolution) -> dict[str, Any]:
    query = resolution.retrieval_query
    lowered = query.lower()
    entity_ok = all(token.lower() in lowered for token in example.must_contain)
    any_ok = True
    if example.must_contain_any:
        any_ok = any(token.lower() in lowered for token in example.must_contain_any)
    forbidden_ok = all(token.lower() not in lowered for token in example.must_not_contain)
    equal_ok = True
    if example.must_equal is not None:
        equal_ok = query == example.must_equal
    rewrite_ok = resolution.rewrite_applied is example.rewrite_required
    followup_ok = True
    if example.expect_followup is not None:
        followup_ok = resolution.followup_detected is example.expect_followup
    complete = entity_ok and any_ok and forbidden_ok and equal_ok
    return {
        "example_id": example.example_id,
        "category": example.category,
        "entity_preservation": entity_ok,
        "standalone_query_completeness": complete,
        "rewrite_required_accuracy": rewrite_ok,
        "followup_detection_ok": followup_ok,
        "retrieval_query": query,
        "rewrite_applied": resolution.rewrite_applied,
        "method": resolution.diagnostics.method,
    }


def evaluate_resolver(
    examples: Sequence[FollowupExample],
    resolver: QueryResolver | None = None,
) -> dict[str, Any]:
    engine = resolver or HeuristicQueryResolver()
    traces = [
        score_resolution(example, engine.resolve(example.question, example.history))
        for example in examples
    ]
    n = len(traces) or 1
    return {
        "resolver_id": engine.resolver_id,
        "n": len(traces),
        "entity_preservation": sum(1 for item in traces if item["entity_preservation"]) / n,
        "standalone_query_completeness": sum(
            1 for item in traces if item["standalone_query_completeness"]
        )
        / n,
        "rewrite_required_accuracy": sum(
            1 for item in traces if item["rewrite_required_accuracy"]
        )
        / n,
        "followup_detection_ok": sum(1 for item in traces if item["followup_detection_ok"])
        / n,
        "traces": traces,
    }
