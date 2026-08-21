"""Deterministic citation extraction, validation, and rendering.

Does not call an LLM. Does not invent provenance.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from research_assistant.context.models import CitationSource, ContextBundle
from research_assistant.generation.models import AnswerCitation, ValidationStatus

PARSER_VERSION = "json.object.v2"
CANONICAL_INSUFFICIENT_ANSWER = (
    "The provided documents do not contain enough evidence to answer this."
)
CITATION_RE = re.compile(r"\[S(\d+)\]")
MARKER_RE = re.compile(r"\[S[^\]]*\]")
BARE_FLAG_RE = re.compile(
    r"^insufficient_evidence\s*[=:]\s*(true|false)\s*$",
    re.IGNORECASE,
)
FENCE_OPEN_RE = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
FENCE_CLOSE_RE = re.compile(r"\s*```$")


@dataclass(frozen=True)
class ExtractedCitations:
    ids: tuple[str, ...]
    counts: dict[str, int]
    malformed_markers: tuple[str, ...]


@dataclass(frozen=True)
class ParsedModelOutput:
    answer: str
    insufficient_evidence: bool
    raw_text: str
    malformed: bool
    error: str | None = None
    structured_citation_ids: tuple[str, ...] = ()
    raw_output_category: str = "malformed_json"
    normalization_applied: tuple[str, ...] = ()
    parser_version: str = PARSER_VERSION
    protocol_status: str = "malformed"
    claim_sources: tuple[tuple[str, tuple[str, ...]], ...] = ()
    sources_disagree: bool | None = None


def extract_citations(text: str) -> ExtractedCitations:
    ids = tuple(f"S{match.group(1)}" for match in CITATION_RE.finditer(text or ""))
    counts: dict[str, int] = {}
    for citation_id in ids:
        counts[citation_id] = counts.get(citation_id, 0) + 1
    malformed = []
    for marker in MARKER_RE.findall(text or ""):
        if not CITATION_RE.fullmatch(marker):
            malformed.append(marker)
    return ExtractedCitations(
        ids=ids,
        counts=counts,
        malformed_markers=tuple(malformed),
    )


def parse_model_output(raw: str) -> ParsedModelOutput:
    original = raw or ""
    norms: list[str] = []
    text = original.replace("\ufeff", "")
    if text != original:
        norms.append("bom")
    stripped = text.strip()
    if stripped != text:
        norms.append("whitespace")
    if not stripped:
        return _malformed(
            original,
            "empty_response",
            "Response was empty",
            norms,
        )

    bare = BARE_FLAG_RE.fullmatch(stripped)
    if bare:
        if bare.group(1).lower() == "true" and not CITATION_RE.search(stripped):
            norms.append("bare_insufficient_true")
            return ParsedModelOutput(
                answer=CANONICAL_INSUFFICIENT_ANSWER,
                insufficient_evidence=True,
                raw_text=original,
                malformed=False,
                structured_citation_ids=(),
                raw_output_category="bare_key_value",
                normalization_applied=tuple(norms),
                protocol_status="recovered",
            )
        return _malformed(
            original,
            "bare_key_value",
            "Bare insufficient_evidence=false is not a complete response",
            norms,
        )

    if stripped.startswith("```"):
        inner = FENCE_OPEN_RE.sub("", stripped, count=1)
        inner = FENCE_CLOSE_RE.sub("", inner)
        stripped = inner.strip()
        norms.append("fence")
        if not stripped:
            return _malformed(
                original,
                "empty_response",
                "Fenced response was empty",
                norms,
            )

    if not stripped.startswith("{"):
        if "{" in stripped:
            return _malformed(
                original,
                "leading_prose",
                "JSON was wrapped in extra prose",
                norms,
            )
        return _malformed(
            original,
            "malformed_json",
            "Response was not a JSON object with answer and insufficient_evidence",
            norms,
        )

    decoder = json.JSONDecoder()
    try:
        payload, index = decoder.raw_decode(stripped)
    except json.JSONDecodeError:
        return _malformed(
            original,
            "malformed_json",
            "Response was not valid JSON",
            norms,
        )
    leftover = stripped[index:].strip()
    if leftover:
        category = "multiple_objects" if leftover.startswith("{") else "trailing_prose"
        return _malformed(
            original,
            category,
            "Response contained more than one JSON object or trailing prose",
            norms,
        )
    if not isinstance(payload, dict):
        return _malformed(
            original,
            "wrong_type",
            "JSON root must be an object",
            norms,
        )
    return _parse_payload(original, payload, norms, fenced="fence" in norms)


def validate_citations(
    answer_text: str,
    bundle: ContextBundle,
    *,
    insufficient_evidence: bool,
    malformed_output: bool,
) -> tuple[ValidationStatus, tuple[AnswerCitation, ...], tuple[str, ...], tuple[str, ...]]:
    extracted = extract_citations(answer_text)
    allowed = {item.citation_id: item.source for item in bundle.items}
    unique_ids = tuple(dict.fromkeys(extracted.ids))
    invalid = tuple(cid for cid in unique_ids if cid not in allowed)
    valid_ids = tuple(cid for cid in unique_ids if cid in allowed)
    citations = tuple(
        AnswerCitation(
            citation_id=cid,
            source=allowed[cid],
            occurrence_count=extracted.counts[cid],
        )
        for cid in valid_ids
    )
    if malformed_output:
        return (
            ValidationStatus.MALFORMED_OUTPUT,
            citations,
            invalid,
            extracted.malformed_markers,
        )
    if extracted.malformed_markers:
        return (
            ValidationStatus.MALFORMED_OUTPUT,
            citations,
            invalid,
            extracted.malformed_markers,
        )
    if invalid:
        return (
            ValidationStatus.INVALID_CITATION,
            citations,
            invalid,
            extracted.malformed_markers,
        )
    if insufficient_evidence:
        return (
            ValidationStatus.INSUFFICIENT_EVIDENCE,
            citations,
            invalid,
            extracted.malformed_markers,
        )
    if not unique_ids and _looks_substantive(answer_text):
        return (
            ValidationStatus.MISSING_CITATIONS,
            citations,
            invalid,
            extracted.malformed_markers,
        )
    return (
        ValidationStatus.VALID,
        citations,
        invalid,
        extracted.malformed_markers,
    )


def render_sources(citations: Sequence[AnswerCitation]) -> str:
    lines = []
    for item in citations:
        lines.append(f"[{item.citation_id}] {item.source.compact_locator()}")
    return "\n".join(lines)


def source_by_id(bundle: ContextBundle, citation_id: str) -> CitationSource | None:
    for item in bundle.items:
        if item.citation_id == citation_id:
            return item.source
    return None


def _looks_substantive(answer_text: str) -> bool:
    return bool(answer_text.strip())


def _structured_citation_ids(payload: dict[str, object]) -> tuple[str, ...]:
    """Diagnostic only. Never used to invent or inject inline markers."""
    for key in ("citation_ids", "citations"):
        value = payload.get(key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return tuple(item for item in value if item)
    return ()


def _optional_claim_sources(
    payload: dict[str, object],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Diagnostic only. Extra field; never required; never injects [S#]."""
    raw = payload.get("claim_sources")
    if not isinstance(raw, list):
        return ()
    out: list[tuple[str, tuple[str, ...]]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        claim = item.get("claim") or item.get("claim_id")
        ids = item.get("source_ids") or item.get("sources")
        if not isinstance(claim, str) or not isinstance(ids, list):
            continue
        source_ids = tuple(str(cid) for cid in ids if isinstance(cid, str) and cid)
        out.append((claim, source_ids))
    return tuple(out)


def _optional_sources_disagree(payload: dict[str, object]) -> bool | None:
    """Diagnostic only. Wrong types are ignored rather than failing the parse."""
    value = payload.get("sources_disagree")
    if isinstance(value, bool):
        return value
    return None


def _protocol_status(malformed: bool, norms: Sequence[str]) -> str:
    if malformed:
        return "malformed"
    if "bare_insufficient_true" in norms or "missing_answer_insufficient_true" in norms:
        return "recovered"
    if any(item in norms for item in ("fence", "bom")):
        return "normalized"
    return "parsed"


def _malformed(
    raw: str,
    category: str,
    error: str,
    norms: Sequence[str],
    *,
    answer: str = "",
    flag: bool = False,
    structured: tuple[str, ...] = (),
) -> ParsedModelOutput:
    return ParsedModelOutput(
        answer=answer,
        insufficient_evidence=flag,
        raw_text=raw,
        malformed=True,
        error=error,
        structured_citation_ids=structured,
        raw_output_category=category,
        normalization_applied=tuple(norms),
        protocol_status="malformed",
    )


def _parse_payload(
    raw: str,
    payload: dict[str, object],
    norms: list[str],
    *,
    fenced: bool,
) -> ParsedModelOutput:
    structured = _structured_citation_ids(payload)
    has_answer = "answer" in payload
    has_flag = "insufficient_evidence" in payload
    answer = payload.get("answer")
    flag = payload.get("insufficient_evidence")
    category = "fenced_json" if fenced else "valid_json"

    if not has_flag:
        return _malformed(
            raw,
            "missing_insufficient_flag",
            "JSON must contain boolean insufficient_evidence",
            norms,
            answer=answer if isinstance(answer, str) else "",
            structured=structured,
        )
    if not isinstance(flag, bool):
        return _malformed(
            raw,
            "wrong_type",
            "insufficient_evidence must be a JSON boolean",
            norms,
            answer=answer if isinstance(answer, str) else "",
            structured=structured,
        )
    if not has_answer:
        if flag is True:
            norms.append("missing_answer_insufficient_true")
            return ParsedModelOutput(
                answer=CANONICAL_INSUFFICIENT_ANSWER,
                insufficient_evidence=True,
                raw_text=raw,
                malformed=False,
                structured_citation_ids=structured,
                raw_output_category=category,
                normalization_applied=tuple(norms),
                protocol_status="recovered",
            )
        return _malformed(
            raw,
            "missing_answer",
            "JSON must contain string answer when insufficient_evidence is false",
            norms,
            structured=structured,
        )
    if not isinstance(answer, str):
        return _malformed(
            raw,
            "wrong_type",
            "answer must be a JSON string",
            norms,
            flag=flag,
            structured=structured,
        )
    if not flag and not answer.strip():
        return _malformed(
            raw,
            "missing_answer",
            "Empty answer with insufficient_evidence=false is not valid",
            norms,
            structured=structured,
        )
    return ParsedModelOutput(
        answer=answer,
        insufficient_evidence=flag,
        raw_text=raw,
        malformed=False,
        structured_citation_ids=structured,
        raw_output_category=category,
        normalization_applied=tuple(norms),
        protocol_status=_protocol_status(False, norms),
        claim_sources=_optional_claim_sources(payload),
        sources_disagree=_optional_sources_disagree(payload),
    )
