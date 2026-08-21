"""Follow-up detection. Conservative: standalone questions pass through."""

from __future__ import annotations

import re

from research_assistant.conversation.pronouns import has_standalone_pronoun

_CONVO_REF = re.compile(
    r"\b(you said|you told|you just|earlier|before that|what about them|"
    r"but you|are you sure|you mentioned)\b",
    re.IGNORECASE,
)
_BARE_WH = re.compile(
    r"^(why|why not|when|where|how|who|what|and then|what happened|"
    r"what happened next)[\s?!.]*$",
    re.IGNORECASE,
)
_FOLLOWUP_PREFIX = re.compile(
    r"^(do they|did they|are they|were they|is it|was it|does it|"
    r"why not|why|when|how come)\b",
    re.IGNORECASE,
)
_PROPER = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")
_DETERMINER_NOUN = re.compile(
    r"\b(this|that|these|those)\s+\w+",
    re.IGNORECASE,
)
_REFERENT_PRONOUN = re.compile(
    r"\b(it|they|them|their|theirs|he|him|his|she|her|hers)\b(?!['’](?:s|re|ll|d|ve|m)\b)",
    re.IGNORECASE,
)


def looks_like_followup(question: str) -> bool:
    text = question.strip()
    if not text:
        return False
    if _CONVO_REF.search(text):
        return True
    stripped = text.rstrip("?!.").strip()
    if _BARE_WH.match(stripped):
        return True
    has_pronoun = has_standalone_pronoun(text)
    has_name = bool(_proper_names_excluding_start(text))
    words = text.split()
    if has_pronoun and not has_name:
        return True
    if _FOLLOWUP_PREFIX.match(text) and not has_name:
        return True
    if len(words) <= 4 and has_pronoun and not has_name:
        return True
    return False


def has_unresolved_pronoun_referent(question: str) -> bool:
    """True when a personal/dummy pronoun needs a referent the question does not name.

    Demonstratives attached to a noun (`this archive`) are not unresolved.
    Named subjects (`When was the Riverton Transit Loop launched?`) are not unresolved.
    This is stricter than `looks_like_followup`, which also matches bare `When`/`Why`
    prefixes without pronouns.
    """
    text = question.strip()
    if not text:
        return False
    if _proper_names_excluding_start(text):
        return False
    stripped = _DETERMINER_NOUN.sub(" ", text)
    return bool(_REFERENT_PRONOUN.search(stripped))


def _proper_names_excluding_start(text: str) -> list[str]:
    """Ignore a single leading capital (normal sentence case)."""
    matches = list(_PROPER.finditer(text))
    names: list[str] = []
    for match in matches:
        if match.start() == 0 and " " not in match.group(0):
            continue
        names.append(match.group(0))
    return names
