import json
from unittest.mock import patch

from research_assistant.context.builder import CitationAwareContextBuilder
from research_assistant.core.settings import (
    DEFAULT_LLM_KEEP_ALIVE,
    DEFAULT_LLM_REPAIR_MODEL,
    Settings,
    load_settings,
)
from research_assistant.generation.identity import LLMIdentity
from research_assistant.generation.models import ChatMessage, LLMRequest, ValidationStatus
from research_assistant.generation.openai_compatible import OpenAICompatibleClient
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.generation.service import GroundedGenerationService
from research_assistant.retrieval.models import RetrievalHit


def _settings(**kwargs) -> Settings:
    values = dict(
        database_path="unused.db",
        log_level="WARNING",
        max_file_bytes=10,
        reranker_model_name="overlap",
        llm_provider="scripted",
        llm_model_name="scripted.v1",
        llm_citation_repair=True,
    )
    values.update(kwargs)
    return Settings(**values)


def _hit(**kwargs) -> RetrievalHit:
    values = dict(
        chunk_id="c1",
        document_id="d1",
        rank=1,
        score=0.2,
        retriever="hybrid",
        text="Self-attention relates distant tokens.",
        page_start=4,
        page_end=5,
        section_path=("Architecture", "Self-Attention"),
        chunker_id="chunker.v1",
        index_id="idx",
        embedding_model_id="emb",
        filename="paper.pdf",
        content_hash="h1",
    )
    values.update(kwargs)
    return RetrievalHit(**values)


def _bundle(*hits: RetrievalHit):
    return CitationAwareContextBuilder(_settings()).build(hits, query="q")


def _json(answer: str, *, evidence: bool = False) -> str:
    return json.dumps({"answer": answer, "insufficient_evidence": evidence})


def test_defaults_do_not_change_keep_alive_or_repair_model() -> None:
    assert DEFAULT_LLM_KEEP_ALIVE == ""
    assert DEFAULT_LLM_REPAIR_MODEL == ""
    settings = Settings(
        database_path="unused.db",
        log_level="WARNING",
        max_file_bytes=10,
    )
    assert settings.llm_keep_alive == ""
    assert settings.llm_repair_model_name == ""


def test_keep_alive_and_repair_model_from_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RESEARCH_ASSISTANT_LLM_KEEP_ALIVE", "30m")
    monkeypatch.setenv("RESEARCH_ASSISTANT_LLM_REPAIR_MODEL", "llama3.2")
    settings = load_settings(database_path=tmp_path / "phase11_6.db")
    assert settings.llm_keep_alive == "30m"
    assert settings.llm_repair_model_name == "llama3.2"


def test_no_repair_when_first_pass_has_valid_citation() -> None:
    main = ScriptedLLM(
        _json("Self-attention relates distant tokens [S1]."),
        generation_ms=4100,
    )
    repair = ScriptedLLM(_json("unused"), generation_ms=5000)
    result = GroundedGenerationService(
        _settings(),
        llm=main,
        repair_llm=repair,
    ).generate("What is self-attention?", _bundle(_hit()))
    assert result.validation_status is ValidationStatus.VALID
    assert result.diagnostics.repair_attempts == 0
    assert result.diagnostics.first_pass_generation_ms == 4100
    assert result.diagnostics.repair_ms == 0
    assert result.diagnostics.generation_ms == 4100
    assert len(main.requests) == 1
    assert repair.requests == []


def test_repair_uses_dedicated_client_when_injected() -> None:
    main = ScriptedLLM(
        _json("Self-attention relates distant tokens."),
        generation_ms=4100,
    )
    repair = ScriptedLLM(
        _json("Self-attention relates distant tokens [S1]."),
        generation_ms=1800,
    )
    result = GroundedGenerationService(
        _settings(llm_repair_model_name="scripted.repair"),
        llm=main,
        repair_llm=repair,
    ).generate("What is self-attention?", _bundle(_hit()))
    assert result.validation_status is ValidationStatus.VALID
    assert result.diagnostics.repair_attempts == 1
    assert result.diagnostics.first_pass_generation_ms == 4100
    assert result.diagnostics.repair_ms == 1800
    assert result.diagnostics.generation_ms == 5900
    assert len(main.requests) == 1
    assert len(repair.requests) == 1
    assert "[S1]" not in result.diagnostics.first_pass_answer_text
    assert "[S1]" in result.answer_text


def test_same_engine_used_when_repair_model_unset() -> None:
    llm = ScriptedLLM(
        (
            _json("Self-attention relates distant tokens."),
            _json("Self-attention relates distant tokens [S1]."),
        ),
        generation_ms=2000,
    )
    result = GroundedGenerationService(_settings(), llm=llm).generate(
        "What is self-attention?", _bundle(_hit())
    )
    assert result.diagnostics.repair_attempts == 1
    assert len(llm.requests) == 2
    assert result.diagnostics.first_pass_generation_ms == 2000
    assert result.diagnostics.repair_ms == 2000
    assert result.diagnostics.generation_ms == 4000


def test_keep_alive_omitted_by_default() -> None:
    captured: dict[str, object] = {}

    class _Resp:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {"content": _json("x", evidence=True)},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    "id": "req-1",
                }
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return _Resp()

    identity = LLMIdentity(
        provider="openai_compatible",
        model_name="qwen2.5-coder:7b",
        temperature=0.0,
        max_output_tokens=512,
        response_format="json_object",
        timeout_seconds=5.0,
        base_url="http://127.0.0.1:9/v1",
    )
    client = OpenAICompatibleClient(
        model_name="qwen2.5-coder:7b",
        base_url="http://127.0.0.1:9/v1",
        timeout_seconds=5.0,
    )
    request = LLMRequest(
        messages=(ChatMessage(role="user", content="{}"),),
        identity=identity,
        allowed_citation_ids=("S1",),
    )
    with patch("research_assistant.generation.openai_compatible.urllib.request.urlopen", fake_urlopen):
        client.generate(request)
    body = captured["body"]
    assert isinstance(body, dict)
    assert "keep_alive" not in body


def test_keep_alive_is_sent_when_configured() -> None:
    captured: dict[str, object] = {}

    class _Resp:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {"content": _json("x", evidence=True)},
                            "finish_reason": "stop",
                        }
                    ]
                }
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode())
        return _Resp()

    identity = LLMIdentity(
        provider="openai_compatible",
        model_name="qwen2.5-coder:7b",
        temperature=0.0,
        max_output_tokens=512,
        response_format="json_object",
        timeout_seconds=5.0,
        base_url="http://127.0.0.1:9/v1",
    )
    client = OpenAICompatibleClient(
        model_name="qwen2.5-coder:7b",
        base_url="http://127.0.0.1:9/v1",
        timeout_seconds=5.0,
        keep_alive="30m",
    )
    request = LLMRequest(
        messages=(ChatMessage(role="user", content="{}"),),
        identity=identity,
        allowed_citation_ids=("S1",),
    )
    with patch("research_assistant.generation.openai_compatible.urllib.request.urlopen", fake_urlopen):
        client.generate(request)
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["keep_alive"] == "30m"


def test_python_still_does_not_auto_append_citations() -> None:
    llm = ScriptedLLM(_json("Self-attention relates distant tokens."))
    result = GroundedGenerationService(
        _settings(llm_citation_repair=False),
        llm=llm,
    ).generate("What is self-attention?", _bundle(_hit()))
    assert result.validation_status is ValidationStatus.MISSING_CITATIONS
    assert "[S1]" not in result.answer_text
    assert result.diagnostics.repair_attempts == 0
    assert result.diagnostics.repair_ms == 0
