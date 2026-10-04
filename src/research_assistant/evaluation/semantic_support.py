"""Evaluation-only lexical overlap, legacy coverage adapter, and repair drift.

None of these diagnostics measures entailment. Production generation is unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from research_assistant.evaluation.quality_metrics import conflict_reported, normalize_text
from research_assistant.generation.citations import CITATION_RE

from research_assistant.evaluation.evidence_metrics import (
    FULL_GOLD_PASSAGE_COVERAGE, PARTIAL_GOLD_PASSAGE_COVERAGE,
    NO_GOLD_PASSAGE_COVERAGE,
)

# Legacy import aliases for old offline scripts; new reports use coverage names.
SUPPORTED = FULL_GOLD_PASSAGE_COVERAGE
PARTIALLY_SUPPORTED = PARTIAL_GOLD_PASSAGE_COVERAGE
UNSUPPORTED = NO_GOLD_PASSAGE_COVERAGE
FULL_LEXICAL_OVERLAP = "FULL_LEXICAL_OVERLAP"
PARTIAL_LEXICAL_OVERLAP = "PARTIAL_LEXICAL_OVERLAP"
NO_LEXICAL_OVERLAP = "NO_LEXICAL_OVERLAP"
POLARITY_MISMATCH = "POLARITY_MISMATCH"
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
    r"\b(no|not|never|cannot|can't|don't|does not|do not|denied|rejected|approved)\b",
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
    """Legacy text-only adapter; deprecated, lacks provenance and is not entailment.

    New reports use classify_cited_gold_coverage on provenance-aware excerpt metrics.
    """
    import warnings
    warnings.warn("Legacy text-only coverage adapter; use provenance-aware cited gold metrics", DeprecationWarning, stacklevel=2)
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


_NEGATIVE = frozenset({"not", "no", "never", "cannot", "denied", "rejected", "without", "unable", "prohibited"})
_POSITIVE = frozenset({"approved", "accepted", "allowed", "authorized", "permitted"})


def _tokens(text: str) -> set[str]:
    text = normalize_text(text).replace("’", "'")
    text = re.sub(r"\b\w+n't\b", "not", text)
    return set(re.findall(r"[a-z]+|\d+(?:[,.]\d+)*", text))


def _explicit_polarities(text: str) -> set[bool]:
    tokens = _tokens(text)
    negative = bool(tokens & _NEGATIVE)
    result = {negative}
    if negative:
        words = re.findall(r"[a-z]+", normalize_text(text))
        negators = {"not", "no", "never", "cannot", "without", "unable"}
        # Conservatively detect both "approved" and "not approved" in one
        # sentence. Nearby negation can be ambiguous; never infer entailment.
        for index, word in enumerate(words):
            if word in _POSITIVE and not set(words[max(0, index - 3):index]) & negators:
                result.add(False)
    return result


def classify_claim_overlap(claim_text: str, cited_texts: Sequence[str]) -> str:
    """Token overlap with conservative explicit polarity/number checks, not entailment.

    Conflicting relevant sentences or double negatives are unclear. This does not
    resolve negation scope, paraphrases, or implicit contradictions.
    """
    content = _tokens(claim_text) - _STOP
    if not content or not any(text.strip() for text in cited_texts):
        return UNCLEAR
    anchors = content - _NEGATIVE - _POSITIVE
    relevant: list[set[str]] = []
    polarities: set[bool] = set()
    for text in cited_texts:
        for sentence in re.split(r"(?<=[.!?;])\s+|\n+", text):
            tokens = _tokens(sentence) - _STOP
            if anchors and len(anchors & tokens) / len(anchors) >= 0.5:
                relevant.append(tokens)
                polarities.update(_explicit_polarities(sentence))
    if not relevant:
        return NO_LEXICAL_OVERLAP
    if len(polarities) > 1:
        return UNCLEAR
    if "not" in content and content & {"denied", "rejected", "prohibited"}:
        return UNCLEAR
    if bool(content & _NEGATIVE) not in polarities:
        return POLARITY_MISMATCH
    # Do not assemble a full claim from words scattered across separate passages.
    ratio = max(len(content & tokens) / len(content) for tokens in relevant)
    numbers = set(_NUMBER_RE.findall(claim_text))
    if any(len(content & tokens) / len(content) >= 0.7 and numbers <= tokens for tokens in relevant):
        return FULL_LEXICAL_OVERLAP
    if ratio >= 0.3:
        return PARTIAL_LEXICAL_OVERLAP
    return NO_LEXICAL_OVERLAP


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
