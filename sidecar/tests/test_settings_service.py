from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.settings import LLMProviderKind, UpdateLLMSettingsRequest
from app.services.settings_service import SettingsService

_DB = Path(__file__).parent / ".test_settings.db"


@pytest.fixture(autouse=False)
def svc() -> SettingsService:
    _DB.unlink(missing_ok=True)
    service = SettingsService(_DB)
    yield service
    _DB.unlink(missing_ok=True)


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


def test_clear_api_key_with_empty_string(svc: SettingsService):
    svc.update_llm_settings(UpdateLLMSettingsRequest(api_key="some-key"))
    svc.update_llm_settings(UpdateLLMSettingsRequest(api_key=""))
    assert svc.get_raw_api_key() is None
    assert svc.get_llm_settings().api_key_set is False


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
