"""Entity extraction and pronoun substitution. History is for referents only."""

from __future__ import annotations

import re
from collections.abc import Sequence

from research_assistant.conversation.models import ConversationTurn
from research_assistant.conversation.pronouns import SUBSTITUTE_PRONOUN

_NAME = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")
_AUX = re.compile(
    r"^(do|did|does|are|is|was|were|can|could|will|would|should)\s+",
    re.IGNORECASE,
)
_LOCATION_OF = re.compile(
    r"\b(?:village|town|city|county|country|kingdom|hamlet|province|"
    r"district|island)\s+of\s+$",
    re.IGNORECASE,
)
_LOCATION_AFTER = re.compile(
    r"^\s+(?:village|town|city|county|country|kingdom|hamlet|hall|"
    r"hollow|street|road|alley|castle|harbour|harbor|river|valley|"
    r"forest|mountain|island|bridge)\b",
    re.IGNORECASE,
)
_LOCATION_LAST = {
    "Hollow",
    "Village",
    "Town",
    "City",
    "Hall",
    "Street",
    "Alley",
    "Castle",
    "Harbour",
    "Harbor",
    "Valley",
    "Forest",
    "Mountain",
    "Island",
    "Bridge",
    "County",
    "Kingdom",
}
_STOP = {
    "The",
    "A",
    "An",
    "This",
    "That",
    "These",
    "Those",
    "If",
    "When",
    "Why",
    "How",
    "Who",
    "What",
    "Where",
    "Do",
    "Did",
    "Does",
    "Is",
    "Are",
    "Was",
    "Were",
    "Not",
    "Yes",
    "No",
    "And",
    "But",
    "Or",
    "In",
    "On",
    "Of",
    "To",
    "For",
    "With",
    "From",
    "About",
    "Whose",
    "Which",
    "There",
    "Then",
    "So",
    "Just",
    "You",
    "Your",
    "I",
    "We",
    "They",
    "He",
    "She",
    "It",
    "Grounded",
    "Insufficient",
    "Unverified",
}


def extract_entities(turns: Sequence[ConversationTurn], *, limit: int = 4) -> tuple[str, ...]:
    """Prefer subjects from recent user questions over answer proper nouns."""
    question_names: list[str] = []
    answer_names: list[str] = []
    for turn in reversed(tuple(turns)):
        for name in _names_in(turn.question, skip_locations=False):
            _absorb(question_names, name)
        for name in _names_in(turn.answer, skip_locations=True):
            _absorb(answer_names, name)
    selected: list[str] = []
    for name in question_names:
        _absorb(selected, name)
        if len(selected) >= limit:
            return tuple(selected)
    if _has_question_subjects(selected):
        return tuple(selected)
    for name in answer_names:
        _absorb(selected, name)
        if len(selected) >= limit:
            break
    return tuple(selected)


def entity_phrase(entities: Sequence[str]) -> str:
    items = [item for item in entities if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def substitute_pronouns(question: str, phrase: str) -> str:
    if not phrase:
        return question
    return SUBSTITUTE_PRONOUN.sub(phrase, question)


def has_explicit_referents(question: str, entities: Sequence[str]) -> bool:
    """True when the current question already names enough entities to stand alone."""
    if len(_names_in(question)) >= 2:
        return True
    hits = 0
    lowered = question or ""
    for entity in entities:
        tokens = [token for token in entity.split() if len(token) >= 2]
        if not tokens:
            continue
        if any(
            re.search(rf"\b{re.escape(token)}\b", lowered, re.IGNORECASE)
            for token in tokens
        ):
            hits += 1
        if hits >= 2:
            return True
    return False


def expand_ellipsis(question: str, *, entities: Sequence[str], previous_question: str) -> str | None:
    stripped = question.strip().rstrip("?!.").strip().lower()
    phrase = entity_phrase(entities)
    topic = previous_question.strip().rstrip("?")
    if stripped in {"why", "why not", "when", "where", "how"}:
        rewritten = _wh_from_previous(stripped, previous_question)
        if rewritten:
            return rewritten
    if stripped in {"why", "why not"}:
        if phrase and topic:
            return f"Why, regarding {phrase} and the question '{topic}'?"
        if phrase:
            return f"Why, regarding {phrase}?"
        if topic:
            return f"Why, regarding the previous question '{topic}'?"
        return None
    if stripped in {"when", "where", "how"}:
        if phrase:
            return f"{stripped.capitalize()} did {phrase}?"
        if topic:
            return f"{stripped.capitalize()}, regarding '{topic}'?"
        return None
    if stripped in {"what happened", "what happened next", "and then"}:
        if phrase:
            return f"What happened next to {phrase}?"
        if topic:
            return f"What happened next regarding '{topic}'?"
        return None
    return None


def _wh_from_previous(wh: str, previous_question: str) -> str | None:
    topic = previous_question.strip().rstrip("?!.").strip()
    if not topic:
        return None
    match = _AUX.match(topic)
    if not match:
        return None
    label = "Why" if wh.startswith("why") else wh.capitalize()
    rest = topic[match.end() :]
    aux = match.group(1).lower()
    return f"{label} {aux} {rest}"


def _names_in(text: str, *, skip_locations: bool = False) -> list[str]:
    names: list[str] = []
    for match in _NAME.finditer(text or ""):
        parts = match.group(1).split()
        consumed = 0
        while parts and parts[0] in _STOP:
            consumed += len(parts[0]) + 1
            parts.pop(0)
        if not parts:
            continue
        token = " ".join(parts)
        start = match.start() + consumed
        end = start + len(token)
        if skip_locations and _is_location_mention(text, start, end, token):
            continue
        names.append(token)
    return names


def _is_location_mention(text: str, start: int, end: int, name: str) -> bool:
    last = name.split()[-1]
    if last in _LOCATION_LAST:
        return True
    if _LOCATION_OF.search(text[:start] or ""):
        return True
    if _LOCATION_AFTER.match(text[end:] or ""):
        return True
    return False


def _has_question_subjects(names: Sequence[str]) -> bool:
    if len(names) >= 2:
        return True
    return any(" " in name for name in names)


def _absorb(found: list[str], name: str) -> None:
    key = name.lower()
    for index, existing in enumerate(found):
        current = existing.lower()
        if key == current:
            return
        if _covers(current, key):
            return
        if _covers(key, current):
            found[index] = name
            return
    found.append(name)


def _covers(longer: str, shorter: str) -> bool:
    if shorter == longer:
        return True
    padded = f" {longer} "
    return f" {shorter} " in padded
