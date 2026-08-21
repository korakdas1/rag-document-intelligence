"""Process-wide settings. Secrets never belong here."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from research_assistant.core.errors import ConfigurationError

DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024
DEFAULT_DATABASE_PATH = Path("data/processed/research_assistant.db")
DEFAULT_UPLOAD_DIR = Path("data/uploads")
DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_EMBEDDING_DEVICE = "auto"
DEFAULT_EMBEDDING_BATCH_SIZE = 32
DEFAULT_VECTOR_INDEX_PATH = Path("data/indexes/qdrant")
DEFAULT_TOP_K = 5
DEFAULT_BM25_K1 = 1.2
DEFAULT_BM25_B = 0.75
DEFAULT_RRF_K = 60
DEFAULT_DENSE_CANDIDATE_K = 20
DEFAULT_LEXICAL_CANDIDATE_K = 20
DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_RERANKER_BATCH_SIZE = 8
DEFAULT_RERANKER_MAX_LENGTH = 512
DEFAULT_RERANK_CANDIDATE_K = 20
DEFAULT_RERANK_TOP_K = 8
DEFAULT_MAX_CONTEXT_TOKENS = 1024
DEFAULT_LLM_PROVIDER = "openai_compatible"
DEFAULT_LLM_MODEL = "qwen2.5-coder:7b"
DEFAULT_LLM_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LLM_TEMPERATURE = 0.0
DEFAULT_LLM_MAX_OUTPUT_TOKENS = 512
DEFAULT_LLM_TIMEOUT_SECONDS = 120.0
DEFAULT_LLM_RESPONSE_FORMAT = "json_object"
DEFAULT_CONVERSATION_WINDOW = 4
DEFAULT_LLM_CITATION_REPAIR = True
DEFAULT_LLM_FORMAT_REPAIR = False
DEFAULT_LLM_KEEP_ALIVE = ""
DEFAULT_LLM_REPAIR_MODEL = ""
DEFAULT_APP_ENV = "development"
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000
DEFAULT_MAX_QUESTION_CHARS = 8000
DEFAULT_HEALTH_PROBE_TIMEOUT_SECONDS = 1.5
DEFAULT_SQLITE_BUSY_TIMEOUT_MS = 5000
VALID_APP_ENVS = frozenset({"development", "test", "production"})
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True)
class Settings:
    database_path: Path
    log_level: str
    max_file_bytes: int
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL
    embedding_device: str = DEFAULT_EMBEDDING_DEVICE
    embedding_batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE
    embedding_normalize: bool = True
    vector_index_path: Path = DEFAULT_VECTOR_INDEX_PATH
    default_top_k: int = DEFAULT_TOP_K
    bm25_k1: float = DEFAULT_BM25_K1
    bm25_b: float = DEFAULT_BM25_B
    rrf_k: int = DEFAULT_RRF_K
    dense_candidate_k: int = DEFAULT_DENSE_CANDIDATE_K
    lexical_candidate_k: int = DEFAULT_LEXICAL_CANDIDATE_K
    reranker_model_name: str = DEFAULT_RERANKER_MODEL
    reranker_device: str = DEFAULT_EMBEDDING_DEVICE
    reranker_batch_size: int = DEFAULT_RERANKER_BATCH_SIZE
    reranker_max_length: int = DEFAULT_RERANKER_MAX_LENGTH
    rerank_candidate_k: int = DEFAULT_RERANK_CANDIDATE_K
    rerank_top_k: int = DEFAULT_RERANK_TOP_K
    rerank_enabled: bool = True
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
    llm_provider: str = DEFAULT_LLM_PROVIDER
    llm_model_name: str = DEFAULT_LLM_MODEL
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_temperature: float = DEFAULT_LLM_TEMPERATURE
    llm_max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS
    llm_timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS
    llm_response_format: str = DEFAULT_LLM_RESPONSE_FORMAT
    upload_dir: Path = DEFAULT_UPLOAD_DIR
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    conversation_window: int = DEFAULT_CONVERSATION_WINDOW
    llm_citation_repair: bool = DEFAULT_LLM_CITATION_REPAIR
    llm_format_repair: bool = DEFAULT_LLM_FORMAT_REPAIR
    llm_keep_alive: str = DEFAULT_LLM_KEEP_ALIVE
    llm_repair_model_name: str = DEFAULT_LLM_REPAIR_MODEL
    app_env: str = DEFAULT_APP_ENV
    api_host: str = DEFAULT_API_HOST
    api_port: int = DEFAULT_API_PORT
    max_question_chars: int = DEFAULT_MAX_QUESTION_CHARS
    health_probe_timeout_seconds: float = DEFAULT_HEALTH_PROBE_TIMEOUT_SECONDS
    sqlite_busy_timeout_ms: int = DEFAULT_SQLITE_BUSY_TIMEOUT_MS


def load_settings(
    *,
    database_path: Path | None = None,
    max_file_bytes: int | None = None,
    log_level: str | None = None,
    embedding_model_name: str | None = None,
    embedding_device: str | None = None,
    embedding_batch_size: int | None = None,
    vector_index_path: Path | None = None,
    default_top_k: int | None = None,
    bm25_k1: float | None = None,
    bm25_b: float | None = None,
    rrf_k: int | None = None,
    dense_candidate_k: int | None = None,
    lexical_candidate_k: int | None = None,
    reranker_model_name: str | None = None,
    reranker_device: str | None = None,
    reranker_batch_size: int | None = None,
    rerank_candidate_k: int | None = None,
    rerank_top_k: int | None = None,
    rerank_enabled: bool | None = None,
    max_context_tokens: int | None = None,
    llm_provider: str | None = None,
    llm_model_name: str | None = None,
    llm_base_url: str | None = None,
    llm_temperature: float | None = None,
    llm_max_output_tokens: int | None = None,
    llm_timeout_seconds: float | None = None,
    llm_keep_alive: str | None = None,
    llm_repair_model_name: str | None = None,
) -> Settings:
    """Load settings from explicit args, then environment, then defaults."""
    path = database_path or _database_path_from_env() or DEFAULT_DATABASE_PATH
    size = (
        max_file_bytes
        if max_file_bytes is not None
        else _env_int(
            "RESEARCH_ASSISTANT_MAX_FILE_BYTES",
            DEFAULT_MAX_FILE_BYTES,
            aliases=("MAX_UPLOAD_BYTES",),
        )
    )
    level = log_level or os.environ.get("LOG_LEVEL") or "INFO"
    model = _coalesce_text(
        embedding_model_name,
        "RESEARCH_ASSISTANT_EMBEDDING_MODEL",
        "EMBEDDING_MODEL",
        default=DEFAULT_EMBEDDING_MODEL,
    )
    device = (
        embedding_device
        or os.environ.get("RESEARCH_ASSISTANT_EMBEDDING_DEVICE")
        or DEFAULT_EMBEDDING_DEVICE
    )
    batch = (
        embedding_batch_size
        if embedding_batch_size is not None
        else _env_int("RESEARCH_ASSISTANT_EMBEDDING_BATCH_SIZE", DEFAULT_EMBEDDING_BATCH_SIZE)
    )
    index_path = (
        vector_index_path
        or _path_from_env("RESEARCH_ASSISTANT_VECTOR_INDEX_PATH")
        or DEFAULT_VECTOR_INDEX_PATH
    )
    top_k = (
        default_top_k
        if default_top_k is not None
        else _env_int("RESEARCH_ASSISTANT_TOP_K", DEFAULT_TOP_K)
    )
    k1 = (
        bm25_k1
        if bm25_k1 is not None
        else _env_float("RESEARCH_ASSISTANT_BM25_K1", DEFAULT_BM25_K1)
    )
    b_param = (
        bm25_b
        if bm25_b is not None
        else _env_float("RESEARCH_ASSISTANT_BM25_B", DEFAULT_BM25_B)
    )
    rrf = (
        rrf_k
        if rrf_k is not None
        else _env_int("RESEARCH_ASSISTANT_RRF_K", DEFAULT_RRF_K)
    )
    dense_depth = (
        dense_candidate_k
        if dense_candidate_k is not None
        else _env_int("RESEARCH_ASSISTANT_DENSE_CANDIDATE_K", DEFAULT_DENSE_CANDIDATE_K)
    )
    lexical_depth = (
        lexical_candidate_k
        if lexical_candidate_k is not None
        else _env_int("RESEARCH_ASSISTANT_LEXICAL_CANDIDATE_K", DEFAULT_LEXICAL_CANDIDATE_K)
    )
    reranker_name = _coalesce_text(
        reranker_model_name,
        "RESEARCH_ASSISTANT_RERANKER_MODEL",
        "RERANKER_MODEL",
        default=DEFAULT_RERANKER_MODEL,
    )
    rerank_device = (
        reranker_device
        or os.environ.get("RESEARCH_ASSISTANT_RERANKER_DEVICE")
        or DEFAULT_EMBEDDING_DEVICE
    )
    rerank_batch = (
        reranker_batch_size
        if reranker_batch_size is not None
        else _env_int("RESEARCH_ASSISTANT_RERANKER_BATCH_SIZE", DEFAULT_RERANKER_BATCH_SIZE)
    )
    rerank_depth = (
        rerank_candidate_k
        if rerank_candidate_k is not None
        else _env_int("RESEARCH_ASSISTANT_RERANK_CANDIDATE_K", DEFAULT_RERANK_CANDIDATE_K)
    )
    rerank_k = (
        rerank_top_k
        if rerank_top_k is not None
        else _env_int("RESEARCH_ASSISTANT_RERANK_TOP_K", DEFAULT_RERANK_TOP_K)
    )
    enabled = rerank_enabled
    if enabled is None:
        enabled = _env_bool(
            os.environ.get("RESEARCH_ASSISTANT_RERANK_ENABLED"),
            default=True,
        )
    context_tokens = (
        max_context_tokens
        if max_context_tokens is not None
        else _env_int("RESEARCH_ASSISTANT_MAX_CONTEXT_TOKENS", DEFAULT_MAX_CONTEXT_TOKENS)
    )
    provider = (
        llm_provider
        or os.environ.get("RESEARCH_ASSISTANT_LLM_PROVIDER")
        or DEFAULT_LLM_PROVIDER
    )
    llm_name = _coalesce_text(
        llm_model_name,
        "RESEARCH_ASSISTANT_LLM_MODEL",
        "LLM_MODEL",
        default=DEFAULT_LLM_MODEL,
    )
    llm_url = _coalesce_text(
        llm_base_url,
        "RESEARCH_ASSISTANT_LLM_BASE_URL",
        "OPENAI_BASE_URL",
        "OLLAMA_BASE_URL",
        default=DEFAULT_LLM_BASE_URL,
    )
    temperature = (
        llm_temperature
        if llm_temperature is not None
        else _env_float("RESEARCH_ASSISTANT_LLM_TEMPERATURE", DEFAULT_LLM_TEMPERATURE)
    )
    max_out = (
        llm_max_output_tokens
        if llm_max_output_tokens is not None
        else _env_int("RESEARCH_ASSISTANT_LLM_MAX_OUTPUT_TOKENS", DEFAULT_LLM_MAX_OUTPUT_TOKENS)
    )
    timeout = (
        llm_timeout_seconds
        if llm_timeout_seconds is not None
        else _env_float(
            "RESEARCH_ASSISTANT_LLM_TIMEOUT_SECONDS",
            DEFAULT_LLM_TIMEOUT_SECONDS,
            aliases=("LLM_TIMEOUT",),
        )
    )
    upload_path = _path_from_env("RESEARCH_ASSISTANT_UPLOAD_DIR") or DEFAULT_UPLOAD_DIR
    origins_env = _first_env("RESEARCH_ASSISTANT_CORS_ORIGINS", "CORS_ALLOWED_ORIGINS")
    if origins_env:
        origins = tuple(item.strip() for item in origins_env.split(",") if item.strip())
    else:
        origins = DEFAULT_CORS_ORIGINS
    window = _env_int(
        "RESEARCH_ASSISTANT_CONVERSATION_WINDOW",
        DEFAULT_CONVERSATION_WINDOW,
    )
    repair = _env_bool(
        os.environ.get("RESEARCH_ASSISTANT_LLM_CITATION_REPAIR"),
        default=DEFAULT_LLM_CITATION_REPAIR,
    )
    format_repair = _env_bool(
        os.environ.get("RESEARCH_ASSISTANT_LLM_FORMAT_REPAIR"),
        default=DEFAULT_LLM_FORMAT_REPAIR,
    )
    keep_alive = _coalesce_text(
        llm_keep_alive,
        "RESEARCH_ASSISTANT_LLM_KEEP_ALIVE",
        default=DEFAULT_LLM_KEEP_ALIVE,
    )
    repair_model = _coalesce_text(
        llm_repair_model_name,
        "RESEARCH_ASSISTANT_LLM_REPAIR_MODEL",
        default=DEFAULT_LLM_REPAIR_MODEL,
    )
    app_env = (
        os.environ.get("APP_ENV") or os.environ.get("RESEARCH_ASSISTANT_APP_ENV") or DEFAULT_APP_ENV
    ).strip().lower()
    api_host = (
        os.environ.get("RESEARCH_ASSISTANT_API_HOST")
        or os.environ.get("API_HOST")
        or DEFAULT_API_HOST
    ).strip()
    api_port = _env_int("RESEARCH_ASSISTANT_API_PORT", DEFAULT_API_PORT, aliases=("API_PORT",))
    max_question = _env_int(
        "RESEARCH_ASSISTANT_MAX_QUESTION_CHARS",
        DEFAULT_MAX_QUESTION_CHARS,
    )
    probe_timeout = _env_float(
        "RESEARCH_ASSISTANT_HEALTH_PROBE_TIMEOUT_SECONDS",
        DEFAULT_HEALTH_PROBE_TIMEOUT_SECONDS,
    )
    busy_ms = _env_int(
        "RESEARCH_ASSISTANT_SQLITE_BUSY_TIMEOUT_MS",
        DEFAULT_SQLITE_BUSY_TIMEOUT_MS,
    )
    settings = Settings(
        database_path=path.expanduser(),
        log_level=level.upper(),
        max_file_bytes=size,
        embedding_model_name=model.strip(),
        embedding_device=device,
        embedding_batch_size=batch,
        embedding_normalize=True,
        vector_index_path=index_path.expanduser(),
        default_top_k=top_k,
        bm25_k1=k1,
        bm25_b=b_param,
        rrf_k=rrf,
        dense_candidate_k=dense_depth,
        lexical_candidate_k=lexical_depth,
        reranker_model_name=reranker_name.strip(),
        reranker_device=rerank_device,
        reranker_batch_size=rerank_batch,
        reranker_max_length=DEFAULT_RERANKER_MAX_LENGTH,
        rerank_candidate_k=rerank_depth,
        rerank_top_k=rerank_k,
        rerank_enabled=enabled,
        max_context_tokens=context_tokens,
        llm_provider=provider.strip(),
        llm_model_name=llm_name.strip(),
        llm_base_url=llm_url.strip().rstrip("/"),
        llm_temperature=temperature,
        llm_max_output_tokens=max_out,
        llm_timeout_seconds=timeout,
        llm_response_format=DEFAULT_LLM_RESPONSE_FORMAT,
        upload_dir=upload_path.expanduser(),
        cors_origins=origins,
        conversation_window=window,
        llm_citation_repair=repair,
        llm_format_repair=format_repair,
        llm_keep_alive=keep_alive.strip(),
        llm_repair_model_name=repair_model.strip(),
        app_env=app_env,
        api_host=api_host,
        api_port=api_port,
        max_question_chars=max_question,
        health_probe_timeout_seconds=probe_timeout,
        sqlite_busy_timeout_ms=busy_ms,
    )
    return validate_settings(settings)


def validate_settings(settings: Settings) -> Settings:
    """Fail clearly on invalid explicit configuration. Do not coerce."""
    if settings.app_env not in VALID_APP_ENVS:
        raise ConfigurationError(
            f"APP_ENV must be one of {sorted(VALID_APP_ENVS)} (got {settings.app_env!r}).",
            code="invalid_config",
        )
    if settings.log_level not in VALID_LOG_LEVELS:
        raise ConfigurationError(
            f"LOG_LEVEL must be one of {sorted(VALID_LOG_LEVELS)} (got {settings.log_level!r}).",
            code="invalid_config",
        )
    if settings.api_port < 1 or settings.api_port > 65535:
        raise ConfigurationError(
            f"API_PORT must be between 1 and 65535 (got {settings.api_port}).",
            code="invalid_config",
        )
    if not settings.api_host.strip():
        raise ConfigurationError("API_HOST must not be empty.", code="invalid_config")
    if settings.max_file_bytes < 1:
        raise ConfigurationError(
            "RESEARCH_ASSISTANT_MAX_FILE_BYTES must be >= 1.",
            code="invalid_config",
        )
    if settings.max_question_chars < 1:
        raise ConfigurationError(
            "RESEARCH_ASSISTANT_MAX_QUESTION_CHARS must be >= 1.",
            code="invalid_config",
        )
    if settings.llm_timeout_seconds <= 0:
        raise ConfigurationError(
            "RESEARCH_ASSISTANT_LLM_TIMEOUT_SECONDS must be > 0.",
            code="invalid_config",
        )
    if settings.health_probe_timeout_seconds <= 0:
        raise ConfigurationError(
            "RESEARCH_ASSISTANT_HEALTH_PROBE_TIMEOUT_SECONDS must be > 0.",
            code="invalid_config",
        )
    if settings.sqlite_busy_timeout_ms < 0:
        raise ConfigurationError(
            "RESEARCH_ASSISTANT_SQLITE_BUSY_TIMEOUT_MS must be >= 0.",
            code="invalid_config",
        )
    if settings.conversation_window < 1:
        raise ConfigurationError(
            "RESEARCH_ASSISTANT_CONVERSATION_WINDOW must be >= 1.",
            code="invalid_config",
        )
    if settings.default_top_k < 1 or settings.dense_candidate_k < 1 or settings.lexical_candidate_k < 1:
        raise ConfigurationError(
            "Retrieval depths (top_k / candidate_k) must be >= 1.",
            code="invalid_config",
        )
    if not settings.llm_model_name:
        raise ConfigurationError("LLM model name must not be empty.", code="invalid_config")
    if not settings.embedding_model_name:
        raise ConfigurationError("Embedding model name must not be empty.", code="invalid_config")
    if not settings.reranker_model_name:
        raise ConfigurationError("Reranker model name must not be empty.", code="invalid_config")
    if not (
        settings.llm_base_url.startswith("http://") or settings.llm_base_url.startswith("https://")
    ):
        raise ConfigurationError(
            "LLM base URL must start with http:// or https://.",
            code="invalid_config",
        )
    if settings.app_env == "production" and any(item.strip() == "*" for item in settings.cors_origins):
        raise ConfigurationError(
            "CORS origin '*' is not allowed when APP_ENV=production. "
            "Set RESEARCH_ASSISTANT_CORS_ORIGINS to explicit origins.",
            code="invalid_config",
        )
    _ensure_writable_parent(settings.database_path, what="database")
    return settings


def _ensure_writable_parent(path: Path, *, what: str) -> None:
    parent = path.expanduser().parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(
            f"Cannot create the {what} directory ({parent}).",
            code="invalid_config",
        ) from exc
    probe = parent / ".research_assistant_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise ConfigurationError(
            f"The {what} directory is not writable ({parent}).",
            code="invalid_config",
        ) from exc


def _coalesce_text(explicit: str | None, *names: str, default: str) -> str:
    if explicit is not None:
        return explicit.strip()
    for name in names:
        if name in os.environ:
            return os.environ[name].strip()
    return default


def _env_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _first_env(*names: str) -> str | None:
    for name in names:
        raw = os.environ.get(name)
        if raw is not None and raw.strip() != "":
            return raw
    return None


def _env_int(name: str, default: int, *, aliases: tuple[str, ...] = ()) -> int:
    raw = _first_env(name, *aliases)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ConfigurationError(
            f"{name} must be an integer (got {raw!r}).",
            code="invalid_config",
        ) from exc


def _env_float(name: str, default: float, *, aliases: tuple[str, ...] = ()) -> float:
    raw = _first_env(name, *aliases)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ConfigurationError(
            f"{name} must be a number (got {raw!r}).",
            code="invalid_config",
        ) from exc


def _path_from_env(name: str) -> Path | None:
    explicit = os.environ.get(name)
    if explicit:
        return Path(explicit)
    return None


def _database_path_from_env() -> Path | None:
    explicit = os.environ.get("RESEARCH_ASSISTANT_DATABASE_PATH") or os.environ.get(
        "DATABASE_PATH"
    )
    if explicit:
        return Path(explicit)
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    if url.startswith("sqlite:///"):
        return Path(url.removeprefix("sqlite:///"))
    raise ConfigurationError(
        "DATABASE_URL must be a sqlite:/// path.",
        code="invalid_config",
    )
