"""LLM identity. Distinct from query text, evidence, and API keys."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMIdentity:
    provider: str
    model_name: str
    temperature: float
    max_output_tokens: int
    response_format: str
    timeout_seconds: float
    base_url: str = ""

    @property
    def llm_id(self) -> str:
        payload = json.dumps(
            {
                "provider": self.provider,
                "model_name": self.model_name,
                "temperature": self.temperature,
                "max_output_tokens": self.max_output_tokens,
                "response_format": self.response_format,
                "timeout_seconds": self.timeout_seconds,
                "base_url": self.base_url,
            },
            sort_keys=True,
        )
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        short_name = self.model_name.rsplit("/", 1)[-1].replace(":", "-")
        return f"{short_name}:{fingerprint}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "llm_id": self.llm_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "response_format": self.response_format,
            "timeout_seconds": self.timeout_seconds,
            "base_url": self.base_url,
        }
