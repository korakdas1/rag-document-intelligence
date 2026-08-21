"""Deterministic subject-completeness scoring. No LLM calls."""

from __future__ import annotations

from collections.abc import Sequence


def subject_completeness(
    answer: str,
    *,
    must_contain: Sequence[str] = (),
    must_not_contain: Sequence[str] = (),
    must_contain_any: bool = False,
) -> bool:
    """True when required participant names appear and distractors do not.

    This scores generated text. It does not invent or inject names.
    """
    lowered = (answer or "").lower()
    required = [item for item in must_contain if item]
    forbidden = [item for item in must_not_contain if item]
    if required:
        if must_contain_any:
            if not any(item.lower() in lowered for item in required):
                return False
        elif not all(item.lower() in lowered for item in required):
            return False
    return all(item.lower() not in lowered for item in forbidden)
