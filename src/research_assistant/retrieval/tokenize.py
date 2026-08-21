"""Deterministic lexical tokenizer for English technical/research text.

Keeps compound identifiers and also emits their alphanumeric parts so
``ERR_CONNECTION_REFUSED`` and ``transformer-based`` both match exact and
partial queries. No stemming, no stopword list.
"""

from __future__ import annotations

import re
import unicodedata

TOKENIZER_ID = "tech.v1"

_APOSTROPHE = str.maketrans({"'": "", "’": "", "‘": "", "`": ""})
# Letters/digits (unicode) with optional ._ - connectors.
_COMPOUND = re.compile(r"[^\W_]+(?:[._-][^\W_]+)*", re.UNICODE)
_PART = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> tuple[str, ...]:
    if not text:
        return ()
    normalized = unicodedata.normalize("NFKC", text).translate(_APOSTROPHE).lower()
    tokens: list[str] = []
    for match in _COMPOUND.finditer(normalized):
        compound = match.group(0)
        tokens.append(compound)
        parts = _PART.findall(compound)
        if len(parts) > 1:
            tokens.extend(parts)
    return tuple(tokens)
