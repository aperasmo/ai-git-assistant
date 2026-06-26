from __future__ import annotations

import logging

from app.llm.base import LLMProvider
from app.llm.prompt import SYSTEM_PROMPT, build_user_message
from app.llm.validator import validate_llm_steps
from app.schemas.repositories import ActionPlanStep, RepositorySnapshot
from app.schemas.settings import LLMProviderKind

logger = logging.getLogger("aiga.llm")


class LLMNotConfiguredError(Exception):
    pass


def _build_provider(settings_service) -> LLMProvider:
    settings = settings_service.get_llm_settings()

    if not settings.provider:
        raise LLMNotConfiguredError("No LLM provider is configured. Open Settings to add one.")

    if settings.provider is LLMProviderKind.OLLAMA:
        from app.llm.ollama_provider import OllamaProvider
        return OllamaProvider(model=settings.model, base_url=settings.base_url)

    api_key = settings_service.get_raw_api_key()
    if not api_key:
        raise LLMNotConfiguredError(
            f"No API key is set for the '{settings.provider}' provider. Open Settings to add one."
        )

    if settings.provider is LLMProviderKind.ANTHROPIC:
        from app.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=api_key, model=settings.model)

    if settings.provider is LLMProviderKind.GEMINI:
        from app.llm.openai_compat_provider import OpenAICompatProvider
        return OpenAICompatProvider(
            api_key=api_key,
            provider="gemini",
            model=settings.model,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

    if settings.provider in (LLMProviderKind.OPENAI, LLMProviderKind.GROQ):
        from app.llm.openai_compat_provider import OpenAICompatProvider
        return OpenAICompatProvider(
            api_key=api_key,
            provider=settings.provider.value,
            model=settings.model,
        )

    raise LLMNotConfiguredError(f"Unsupported provider: '{settings.provider}'.")


class LLMRouter:
    def __init__(self, settings_service) -> None:
        self._settings_service = settings_service

    def plan(self, message: str, snapshot: RepositorySnapshot) -> list[ActionPlanStep]:
        provider = _build_provider(self._settings_service)
        user_message = build_user_message(message, snapshot)

        try:
            raw_steps = provider.complete(SYSTEM_PROMPT, user_message)
        except LLMNotConfiguredError:
            raise
        except Exception as exc:
            logger.exception("LLM provider call failed")
            raise RuntimeError(f"The AI call failed: {exc}") from exc

        return validate_llm_steps(raw_steps, snapshot)
