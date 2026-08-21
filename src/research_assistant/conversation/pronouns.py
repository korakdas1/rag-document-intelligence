"""Standalone pronoun matching. Contractions are not pronouns."""

from __future__ import annotations

import re

# Apostrophe is a non-word character, so \bit\b matches the "it" in "it's".
# Negative lookahead keeps it's / that's / he's / they're intact.
_CONTRACTION_TAIL = r"['’](?:s|re|ll|d|ve|m)\b"

_DETECT_NAMES = (
    r"they|them|their|theirs|he|him|his|she|her|hers|it|its|"
    r"this|that|those|these"
)
# Dummy/expletive "it" ("Is it a happy ending?") is not a personal referent.
# Substituting it with a name phrase produced ungrammatical generation queries.
_SUBSTITUTE_NAMES = r"they|them|their|theirs|he|him|his|she|her|hers"

DETECT_PRONOUN = re.compile(
    rf"\b({_DETECT_NAMES})\b(?!{_CONTRACTION_TAIL})",
    re.IGNORECASE,
)
SUBSTITUTE_PRONOUN = re.compile(
    rf"\b({_SUBSTITUTE_NAMES})\b(?!{_CONTRACTION_TAIL})",
    re.IGNORECASE,
)


def has_standalone_pronoun(text: str) -> bool:
    return bool(DETECT_PRONOUN.search(text or ""))
