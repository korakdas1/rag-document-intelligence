"""Chunking knobs. Defaults are development starting points, not claimed optima."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

# Development defaults. Not evaluated against retrieval quality.
DEFAULT_TARGET_CHARS = 1000
DEFAULT_MAX_CHARS = 1500
DEFAULT_MIN_CHARS = 200
DEFAULT_OVERLAP_CHARS = 150
CHUNKER_VERSION = "v1"


@dataclass(frozen=True)
class ChunkingConfig:
    strategy: str = "structure"
    target_chars: int = DEFAULT_TARGET_CHARS
    max_chars: int = DEFAULT_MAX_CHARS
    min_chars: int = DEFAULT_MIN_CHARS
    overlap_chars: int = DEFAULT_OVERLAP_CHARS
    prefer_section_boundaries: bool = True

    def __post_init__(self) -> None:
        if self.strategy not in {"structure", "window"}:
            raise ValueError(f"Unknown chunking strategy: {self.strategy}")
        if not (0 < self.min_chars <= self.target_chars <= self.max_chars):
            raise ValueError(
                "Require 0 < min_chars <= target_chars <= max_chars; "
                f"got min={self.min_chars} target={self.target_chars} max={self.max_chars}"
            )
        if not (0 <= self.overlap_chars < self.target_chars):
            raise ValueError(
                "Require 0 <= overlap_chars < target_chars; "
                f"got overlap={self.overlap_chars} target={self.target_chars}"
            )

    @property
    def chunker_id(self) -> str:
        """Algorithm version plus config fingerprint so experiments are reconstructable."""
        payload = json.dumps(
            {
                "strategy": self.strategy,
                "target_chars": self.target_chars,
                "max_chars": self.max_chars,
                "min_chars": self.min_chars,
                "overlap_chars": self.overlap_chars,
                "prefer_section_boundaries": self.prefer_section_boundaries,
                "version": CHUNKER_VERSION,
            },
            sort_keys=True,
        )
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        return f"{self.strategy}.{CHUNKER_VERSION}:{fingerprint}"


def default_config(*, strategy: str = "structure") -> ChunkingConfig:
    return ChunkingConfig(strategy=strategy)
