from pathlib import Path

import pytest

from research_assistant.core.settings import load_settings


@pytest.mark.parametrize("app_env", ["development", "production"])
def test_native_api_defaults_to_loopback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, app_env: str
) -> None:
    monkeypatch.setenv("APP_ENV", app_env)
    for name in (
        "API_HOST", "RESEARCH_ASSISTANT_API_HOST",
        "RESEARCH_ASSISTANT_CORS_ORIGINS", "CORS_ALLOWED_ORIGINS",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings(database_path=tmp_path / "docs.db")
    assert settings.api_host == "127.0.0.1"


def test_production_allows_internal_container_bind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("RESEARCH_ASSISTANT_API_HOST", raising=False)
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("RESEARCH_ASSISTANT_CORS_ORIGINS", "http://127.0.0.1:8000")
    settings = load_settings(database_path=tmp_path / "docs.db")
    assert settings.api_host == "0.0.0.0"
    assert settings.cors_origins == ("http://127.0.0.1:8000",)
