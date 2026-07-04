from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.llm.base import LLMProvider
from app.llm.prompt import (
    CHANGE_SUMMARY_SYSTEM_PROMPT,
    COMMIT_MESSAGE_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_change_summary_user_message,
    build_commit_message_user_message,
    build_user_message,
)
from app.llm.validator import validate_llm_steps
from app.schemas.repositories import ActionPlanStep, CommitSuggestion, GenerateChangeSummaryResponse, RepositorySnapshot
from app.schemas.settings import LLMProviderKind

logger = logging.getLogger("aiga.llm")


class LLMNotConfiguredError(Exception):
    pass


@dataclass(frozen=True)
class CommitMessageDraft:
    subject: str
    body: list[str]
    warning: str | None = None
    confidence: str = "medium"
    detected_scope: list[str] | None = None
    alternatives: list[str] | None = None

    @property
    def message(self) -> str:
        if not self.body:
            return self.subject
        return self.subject + "\n\n" + "\n".join(f"- {item}" for item in self.body)


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

    def commit_message(self, *, branch: str | None, diff_context: str, style: str = "detailed") -> CommitMessageDraft:
        provider = _build_provider(self._settings_service)
        user_message = build_commit_message_user_message(
            branch=branch,
            diff_context=diff_context,
            style=style,
        )

        try:
            raw = provider.complete_text(
                COMMIT_MESSAGE_SYSTEM_PROMPT,
                user_message,
                max_tokens=280,
            )
        except LLMNotConfiguredError:
            raise
        except Exception as exc:
            logger.exception("LLM commit-message call failed")
            raise RuntimeError(f"The AI call failed: {exc}") from exc

        return _parse_commit_message_draft(raw)

    def change_summary(
        self,
        *,
        branch: str | None,
        diff_context: str,
        context_summary: str,
    ) -> GenerateChangeSummaryResponse:
        provider = _build_provider(self._settings_service)
        user_message = build_change_summary_user_message(
            branch=branch,
            diff_context=diff_context,
        )

        try:
            raw = provider.complete_text(
                CHANGE_SUMMARY_SYSTEM_PROMPT,
                user_message,
                max_tokens=900,
            )
        except LLMNotConfiguredError:
            raise
        except Exception as exc:
            logger.exception("LLM change-summary call failed")
            raise RuntimeError(f"The AI call failed: {exc}") from exc

        parsed = _parse_change_summary_json(raw)
        return GenerateChangeSummaryResponse(
            branch_summary=_clean_text(parsed.get("branch_summary"), "Changes are ready for review."),
            file_summaries=_clean_list(parsed.get("file_summaries"))[:20],
            pr_title=_normalise_title(parsed.get("pr_title"), "Update project changes"),
            pr_body=_clean_text(parsed.get("pr_body"), "Summary:\n- Review the selected changes."),
            commit_suggestions=_normalise_commit_suggestions(parsed.get("commit_suggestions")),
            context_summary=context_summary,
        )


def _normalise_commit_subject(value: str) -> str:
    first_line = next((line.strip() for line in value.splitlines() if line.strip()), "")
    first_line = first_line.strip().strip("`\"'")

    prefixes = ("commit message:", "subject:", "message:")
    lowered = first_line.lower()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            first_line = first_line[len(prefix):].strip().strip("`\"'")
            break

    if not first_line:
        raise RuntimeError("The AI did not return a commit message.")
    if "\x00" in first_line:
        raise RuntimeError("The AI returned an invalid commit message.")
    if len(first_line) > 72:
        first_line = first_line[:72].rstrip()
    return first_line


def _parse_commit_message_draft(value: str) -> CommitMessageDraft:
    parsed = _parse_json_object(value)
    if parsed:
        subject = _normalise_commit_subject(str(parsed.get("subject", "")))
        body = _clean_list(parsed.get("body"))[:5]
        warning = _clean_optional_text(parsed.get("warning"), limit=300)
        confidence = _normalise_confidence(parsed.get("confidence"))
        detected_scope = _clean_list(parsed.get("detected_scope"))[:8]
        alternatives = [
            _normalise_commit_subject(item)
            for item in _clean_list(parsed.get("alternatives"))[:3]
            if item.strip()
        ]
        return CommitMessageDraft(
            subject=subject,
            body=body,
            warning=warning,
            confidence=confidence,
            detected_scope=detected_scope,
            alternatives=alternatives,
        )

    # Preserve useful AI commit body text when providers return plain text.
    lines = [line.strip().strip("`") for line in value.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("The AI did not return a commit message.")

    subject = _normalise_commit_subject(lines[0])
    body: list[str] = []
    for line in lines[1:]:
        cleaned = line.lstrip("-* ").strip()
        if cleaned:
            body.append(cleaned[:500])
    return CommitMessageDraft(subject=subject, body=body[:5], confidence="medium", detected_scope=[], alternatives=[])


def _parse_change_summary_json(value: str) -> dict:
    parsed = _parse_json_object(value)
    if parsed is not None:
        return parsed

    return {
        "branch_summary": value.strip()[:1000] or "Changes are ready for review.",
        "file_summaries": [],
        "pr_title": "Update project changes",
        "pr_body": value.strip()[:3000] or "Summary:\n- Review the selected changes.",
        "commit_suggestions": [],
    }


def _parse_json_object(value: str) -> dict | None:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def _clean_text(value, fallback: str, limit: int = 4000) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = value.strip()
    return cleaned[:limit].rstrip() if cleaned else fallback


def _clean_optional_text(value, limit: int = 4000) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned[:limit].rstrip() if cleaned else None


def _normalise_confidence(value) -> str:
    if not isinstance(value, str):
        return "medium"
    cleaned = value.strip().lower()
    return cleaned if cleaned in {"low", "medium", "high"} else "medium"


def _clean_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip()[:500])
    return result


def _normalise_title(value, fallback: str) -> str:
    title = _clean_text(value, fallback, limit=120).splitlines()[0].strip().strip("`\"'")
    return title[:120].rstrip() or fallback


def _normalise_commit_suggestions(value) -> list[CommitSuggestion]:
    if not isinstance(value, list):
        return []

    suggestions: list[CommitSuggestion] = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        message = _clean_text(item.get("message"), "", limit=120)
        if not message:
            continue
        suggestions.append(
            CommitSuggestion(
                message=_normalise_commit_subject(message),
                files=_clean_list(item.get("files"))[:20],
                rationale=_clean_text(item.get("rationale"), "", limit=500),
            )
        )
    return suggestions
