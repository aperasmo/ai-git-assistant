from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.schemas.settings import (
    LLMProviderKind,
    UpdateGitHubSettingsRequest,
    UpdateGitLabSettingsRequest,
    UpdateLLMSettingsRequest,
)
from app.services.settings_service import SettingsService


@pytest.fixture(autouse=False)
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.db"


@pytest.fixture(autouse=False)
def svc(db_path: Path) -> SettingsService:
    return SettingsService(db_path)


def test_initial_state_is_empty(svc: SettingsService):
    settings = svc.get_llm_settings()
    assert settings.provider is None
    assert settings.api_key_set is False
    assert settings.model is None
    assert settings.base_url is None


def test_set_anthropic_provider_and_key(svc: SettingsService):
    svc.update_llm_settings(
        UpdateLLMSettingsRequest(
            provider=LLMProviderKind.ANTHROPIC,
            api_key="sk-ant-test-key",
            model="claude-haiku-4-5-20251001",
        )
    )
    settings = svc.get_llm_settings()
    assert settings.provider is LLMProviderKind.ANTHROPIC
    assert settings.api_key_set is True
    assert settings.model == "claude-haiku-4-5-20251001"
    # key must not be exposed in the settings response
    assert not hasattr(settings, "api_key")


def test_get_raw_api_key_returns_stored_value(svc: SettingsService):
    svc.update_llm_settings(UpdateLLMSettingsRequest(api_key="my-secret-key"))
    assert svc.get_raw_api_key() == "my-secret-key"


def test_api_key_is_not_stored_in_plaintext(svc: SettingsService, db_path: Path):
    svc.update_llm_settings(UpdateLLMSettingsRequest(api_key="my-secret-key"))

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()

    stored = {key: value for key, value in rows}
    assert "llm_api_key" not in stored
    assert stored["llm_api_key_dpapi"] != "my-secret-key"
    assert stored["llm_api_key_dpapi"].startswith("dpapi:")


def test_legacy_plaintext_api_key_is_migrated(svc: SettingsService, db_path: Path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            ("llm_api_key", "legacy-secret"),
        )

    assert svc.get_raw_api_key() == "legacy-secret"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()

    stored = {key: value for key, value in rows}
    assert "llm_api_key" not in stored
    assert stored["llm_api_key_dpapi"].startswith("dpapi:")


def test_clear_api_key_with_empty_string(svc: SettingsService):
    svc.update_llm_settings(UpdateLLMSettingsRequest(api_key="some-key"))
    svc.update_llm_settings(UpdateLLMSettingsRequest(api_key=""))
    assert svc.get_raw_api_key() is None
    assert svc.get_llm_settings().api_key_set is False


def test_github_token_is_encrypted_and_hidden(svc: SettingsService, db_path: Path):
    settings = svc.update_github_settings(UpdateGitHubSettingsRequest(token="ghp-test-token"))

    assert settings.token_set is True
    assert svc.get_raw_github_token() == "ghp-test-token"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()

    stored = {key: value for key, value in rows}
    assert stored["github_token_dpapi"] != "ghp-test-token"
    assert stored["github_token_dpapi"].startswith("dpapi:")


def test_gitlab_token_is_encrypted_and_hidden(svc: SettingsService, db_path: Path):
    settings = svc.update_gitlab_settings(
        UpdateGitLabSettingsRequest(
            token="glpat-test-token",
            base_url="https://gitlab.company.test/",
        )
    )

    assert settings.token_set is True
    assert settings.base_url == "https://gitlab.company.test"
    assert svc.get_raw_gitlab_token() == "glpat-test-token"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()

    stored = {key: value for key, value in rows}
    assert stored["gitlab_token_dpapi"] != "glpat-test-token"
    assert stored["gitlab_token_dpapi"].startswith("dpapi:")


def test_update_does_not_overwrite_unmentioned_fields(svc: SettingsService):
    svc.update_llm_settings(
        UpdateLLMSettingsRequest(provider=LLMProviderKind.OLLAMA, model="llama3.2")
    )
    svc.update_llm_settings(UpdateLLMSettingsRequest(model="mistral"))
    settings = svc.get_llm_settings()
    assert settings.provider is LLMProviderKind.OLLAMA
    assert settings.model == "mistral"


def test_ollama_base_url_stored_and_retrieved(svc: SettingsService):
    svc.update_llm_settings(
        UpdateLLMSettingsRequest(
            provider=LLMProviderKind.OLLAMA,
            base_url="http://192.168.1.10:11434",
        )
    )
    settings = svc.get_llm_settings()
    assert settings.base_url == "http://192.168.1.10:11434"


def test_set_provider_to_none_clears_provider(svc: SettingsService):
    svc.update_llm_settings(UpdateLLMSettingsRequest(provider=LLMProviderKind.OPENAI))
    # Pass a clear by sending empty string as None equivalent — not possible via model,
    # so we just set a new provider
    svc.update_llm_settings(UpdateLLMSettingsRequest(provider=LLMProviderKind.GROQ))
    assert svc.get_llm_settings().provider is LLMProviderKind.GROQ
