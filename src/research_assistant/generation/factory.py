"""Construct an LLMClient from settings. Scripted is for tests/CI only."""

from __future__ import annotations

import os

from research_assistant.core.settings import Settings
from research_assistant.generation.openai_compatible import OpenAICompatibleClient
from research_assistant.generation.protocol import LLMClient
from research_assistant.generation.scripted import ScriptedLLM


def llm_from_settings(
    settings: Settings,
    *,
    model_name: str | None = None,
) -> LLMClient:
    provider = settings.llm_provider.strip().lower()
    model = (model_name or settings.llm_model_name).strip()
    if provider in {"scripted", "fake"} or model.startswith("scripted"):
        return ScriptedLLM()
    api_key = (
        os.environ.get("RESEARCH_ASSISTANT_LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    )
    return OpenAICompatibleClient(
        model_name=model,
        base_url=settings.llm_base_url,
        api_key=api_key,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
        timeout_seconds=settings.llm_timeout_seconds,
        response_format=settings.llm_response_format,
        keep_alive=settings.llm_keep_alive,
    )
