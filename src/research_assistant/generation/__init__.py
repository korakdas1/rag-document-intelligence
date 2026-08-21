"""Grounded LLM generation from ContextBundle. Does not retrieve."""

from research_assistant.generation.citations import extract_citations, parse_model_output, render_sources
from research_assistant.generation.identity import LLMIdentity
from research_assistant.generation.models import GroundedAnswer, LLMRequest, LLMResponse, ValidationStatus
from research_assistant.generation.openai_compatible import OpenAICompatibleClient
from research_assistant.generation.protocol import LLMClient
from research_assistant.generation.rag import RAGResult, RAGService
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.generation.service import GroundedGenerationService

__all__ = [
    "GroundedAnswer",
    "GroundedGenerationService",
    "LLMClient",
    "LLMIdentity",
    "LLMRequest",
    "LLMResponse",
    "OpenAICompatibleClient",
    "RAGResult",
    "RAGService",
    "ScriptedLLM",
    "ValidationStatus",
    "extract_citations",
    "parse_model_output",
    "render_sources",
]
