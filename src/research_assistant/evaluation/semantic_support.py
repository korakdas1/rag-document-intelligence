"""Eval-only semantic citation support and repair-drift helpers.

Not used in production generation. Gold labels are authoritative.
Lexical overlap is a lower bound, not entailment.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from research_assistant.evaluation.quality_metrics import conflict_reported, normalize_text
from research_assistant.generation.citations import CITATION_RE

SUPPORTED = "SUPPORTED"
PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
UNCLEAR = "UNCLEAR"

_MARKER_SPACE_RE = re.compile(r"\s+([.,;:])")


def _body_without_markers(text: str) -> str:
    stripped = CITATION_RE.sub(" ", text or "")
    stripped = _MARKER_SPACE_RE.sub(r"\1", stripped)
    return normalize_text(stripped)

_DATE_RE = re.compile(
    r"\b\d{1,2}\s+(january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{4}\b|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b")
_POLARITY_RE = re.compile(
    r"\b(no|not|never|cannot|can't|don't|does not|do not|denied|approved)\b",
    re.IGNORECASE,
)
_ENTITYISH_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")


def claim_spans(answer: str) -> list[dict[str, Any]]:
    """Split answer into claim text attached to following [S#] markers."""
    text = answer or ""
    spans: list[dict[str, Any]] = []
    last = 0
    for match in CITATION_RE.finditer(text):
        claim = text[last : match.start()].strip(" ,;.")
        source_id = f"S{match.group(1)}"
        if spans and not claim:
            ids = list(spans[-1]["source_ids"])
            ids.append(source_id)
            spans[-1]["source_ids"] = tuple(dict.fromkeys(ids))
        else:
            spans.append({"claim": claim, "source_ids": (source_id,)})
        last = match.end()
    trailing = text[last:].strip(" ,;.")
    if trailing:
        spans.append({"claim": trailing, "source_ids": ()})
    return spans


def gold_in_texts(gold_text: str, cited_texts: Sequence[str]) -> bool:
    needle = normalize_text(gold_text)
    if not needle:
        return False
    return any(needle in normalize_text(body) for body in cited_texts if body)


def classify_cited_support(
    *,
    product_status: str | None,
    gold_passages: Sequence[str],
    cited_texts: Sequence[str],
    has_valid_citation: bool,
) -> str:
    """Question-level support: do cited passages contain gold, not merely a valid ID."""
    if product_status != "GROUNDED" or not has_valid_citation:
        return UNCLEAR
    needles = [text for text in gold_passages if str(text).strip()]
    if not needles:
        return UNCLEAR
    hits = sum(1 for text in needles if gold_in_texts(text, cited_texts))
    if hits == 0:
        return UNSUPPORTED
    if hits < len(needles):
        return PARTIALLY_SUPPORTED
    return SUPPORTED


def classify_claim_support(
    claim_text: str,
    cited_texts: Sequence[str],
) -> str:
    """Utterance-level lower bound: claim tokens vs cited passage. Not entailment."""
    body = normalize_text(claim_text)
    if not body or not cited_texts:
        return UNCLEAR
    joined = " ".join(normalize_text(item) for item in cited_texts)
    if not joined:
        return UNCLEAR
    tokens = [tok for tok in re.findall(r"[a-z0-9]+", body) if len(tok) > 2]
    content = [tok for tok in tokens if tok not in _STOP]
    if not content:
        return UNCLEAR
    overlap = sum(1 for tok in content if tok in joined)
    ratio = overlap / len(content)
    if ratio >= 0.7:
        return SUPPORTED
    if ratio >= 0.3:
        return PARTIALLY_SUPPORTED
    return UNSUPPORTED


_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "was",
        "were",
        "with",
        "that",
        "this",
        "from",
        "not",
        "are",
        "has",
        "had",
        "does",
        "did",
        "into",
        "than",
        "then",
        "also",
        "only",
        "over",
        "after",
        "before",
        "between",
        "without",
        "about",
        "their",
        "there",
        "which",
        "while",
        "using",
        "used",
    }
)


def repair_drift(first: str, final: str) -> dict[str, Any]:
    """Deterministic first-pass vs repaired-text comparison. Not an LLM judge."""
    a = first or ""
    b = final or ""
    if a.strip() == b.strip():
        return {"changed": False, "kinds": []}
    kinds: list[str] = []
    a_markers = CITATION_RE.findall(a)
    b_markers = CITATION_RE.findall(b)
    a_body = _body_without_markers(a)
    b_body = _body_without_markers(b)
    if a_body == b_body and a_markers != b_markers:
        kinds.append("marker_only")
    dates_a = {match.group(0).lower() for match in _DATE_RE.finditer(a)}
    dates_b = {match.group(0).lower() for match in _DATE_RE.finditer(b)}
    if dates_a != dates_b:
        kinds.append("date_change")
    nums_a = set(_NUMBER_RE.findall(a))
    nums_b = set(_NUMBER_RE.findall(b))
    if nums_a != nums_b:
        kinds.append("number_change")
    pol_a = {m.group(0).lower() for m in _POLARITY_RE.finditer(a)}
    pol_b = {m.group(0).lower() for m in _POLARITY_RE.finditer(b)}
    if pol_a != pol_b:
        kinds.append("polarity_change")
    ent_a = set(_ENTITYISH_RE.findall(a))
    ent_b = set(_ENTITYISH_RE.findall(b))
    if ent_a != ent_b and "marker_only" not in kinds:
        kinds.append("entity_change")
    conflict_a = conflict_reported(a)
    conflict_b = conflict_reported(b)
    if conflict_a and not conflict_b:
        kinds.append("conflict_removal")
    if not kinds:
        kinds.append("paraphrase")
    if len(b_body.split()) > len(a_body.split()) + 4:
        kinds.append("added_factual_claim")
    if len(a_body.split()) > len(b_body.split()) + 4:
        kinds.append("removed_factual_claim")
    return {"changed": True, "kinds": kinds}


def support_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    grounded = [row for row in rows if row.get("product_status") == "GROUNDED"]
    counts = {SUPPORTED: 0, PARTIALLY_SUPPORTED: 0, UNSUPPORTED: 0, UNCLEAR: 0}
    for row in grounded:
        label = row.get("support_class") or UNCLEAR
        counts[label] = counts.get(label, 0) + 1
    n = len(grounded)
    return {
        "product_grounded": n,
        "supported": counts[SUPPORTED],
        "partially_supported": counts[PARTIALLY_SUPPORTED],
        "unsupported": counts[UNSUPPORTED],
        "unclear": counts[UNCLEAR],
        "fully_supported_cited_rate": (counts[SUPPORTED] / n) if n else None,
        "unsupported_cited_rate": (counts[UNSUPPORTED] / n) if n else None,
    }
