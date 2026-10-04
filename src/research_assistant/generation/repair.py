"""Fail-closed citation repair. No answer rewriting or general text normalization."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from research_assistant.context.models import ContextBundle
from research_assistant.generation.citations import (
    ParsedModelOutput,
    parse_model_output,
    validate_citations,
)
from research_assistant.generation.models import ValidationStatus

_INSERTION = re.compile(r" *\[S(\d+)\] *")


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"Not a JSON constant: {value}")


def preserves_answer_content(
    original: str, repaired: str, allowed_citation_ids: tuple[str, ...]
) -> bool:
    """Reconstruct the uncited original by deleting valid markers and adjacent spaces.

    Only ASCII spaces immediately beside markers may be deleted. Every original
    character must survive in order, including all original spaces, punctuation,
    tabs, newlines and Unicode characters. No case folding or whitespace collapse.
    Original offsets retain ambiguity about which adjacent spaces were inserted;
    accepting requires at least one exact reconstruction of the entire original.
    """
    positions = {0}
    previous_end = 0
    for marker in _INSERTION.finditer(repaired):
        citation_id = f"S{marker.group(1)}"
        if citation_id not in allowed_citation_ids:
            return False
        literal = repaired[previous_end:marker.start()]
        adjacent_spaces = len(marker.group()) - len(f"[{citation_id}]")
        next_positions: set[int] = set()
        for position in positions:
            if not original.startswith(literal, position):
                continue
            position += len(literal)
            next_positions.add(position)
            for _ in range(adjacent_spaces):
                if position == len(original) or original[position] != " ":
                    break
                position += 1
                next_positions.add(position)
        if not next_positions:
            return False
        positions = next_positions
        previous_end = marker.end()
    suffix = repaired[previous_end:]
    return any(original[position:] == suffix for position in positions)


@dataclass(frozen=True)
class CitationRepairValidation:
    parsed: ParsedModelOutput
    rejection_reason: str = ""
    content_preserved: bool = False

    @property
    def accepted(self) -> bool:
        return not self.rejection_reason


def validate_citation_repair(
    original_answer: str, raw_output: str, bundle: ContextBundle
) -> CitationRepairValidation:
    """Require plain JSON, valid inline citations, false flag and exact content.

    The shared first-pass parser is unchanged. Repair additionally requires valid
    JSON directly, so parser recovery cannot conceal modifications to answer text.
    Reasons have deterministic precedence: format, IDs, flag, missing, content.
    """
    parsed = parse_model_output(raw_output)
    try:
        payload = json.loads(raw_output, parse_constant=_reject_non_json_constant)
    except (ValueError, TypeError):
        return CitationRepairValidation(parsed, "malformed_output")
    if parsed.malformed or not isinstance(payload, dict):
        return CitationRepairValidation(parsed, "malformed_output")
    raw_answer = payload.get("answer")
    allowed = tuple(item.citation_id for item in bundle.items)
    preserved = (
        isinstance(raw_answer, str)
        and raw_answer == parsed.answer
        and preserves_answer_content(original_answer, raw_answer, allowed)
    )
    status, citations, invalid, malformed = validate_citations(
        parsed.answer,
        bundle,
        insufficient_evidence=parsed.insufficient_evidence,
        malformed_output=parsed.malformed,
    )
    if invalid or malformed:
        reason = "invalid_citation"
    elif parsed.insufficient_evidence:
        reason = "insufficient_flag_changed"
    elif not citations or status is ValidationStatus.MISSING_CITATIONS:
        reason = "missing_citations_after_repair"
    elif not preserved:
        reason = "content_changed"
    else:
        reason = ""
    return CitationRepairValidation(parsed, reason, preserved)
