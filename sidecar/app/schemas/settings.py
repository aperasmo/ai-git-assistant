from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from .base import ApiModel


class LLMProviderKind(StrEnum):
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    OPENAI = "openai"
    GROQ = "groq"


class LLMSettings(ApiModel):
    provider: LLMProviderKind | None = None
    api_key_set: bool = False
    model: str | None = None
    base_url: str | None = None


class UpdateLLMSettingsRequest(ApiModel):
    provider: LLMProviderKind | None = None
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None


class SetExternalLLMRequest(ApiModel):
    allowed: bool
