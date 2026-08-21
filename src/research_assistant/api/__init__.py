"""HTTP product API. Thin DTOs over existing application services. No RAG logic."""

from research_assistant.api.app import create_api

__all__ = ["create_api"]
