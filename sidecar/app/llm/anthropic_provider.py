from __future__ import annotations

from app.llm.base import LLMProvider
from app.llm.prompt import PLAN_TOOL

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "The 'anthropic' package is not installed in the sidecar. "
                "Rebuild with: npm run sidecar:build"
            ) from exc

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model or _DEFAULT_MODEL

    def ping(self) -> None:
        self._client.messages.create(
            model=self._model,
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )

    def complete_text(self, system_prompt: str, user_message: str, *, max_tokens: int = 120) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)

        text = "\n".join(parts).strip()
        if not text:
            raise RuntimeError("The AI did not return text.")
        return text

    def complete(self, system_prompt: str, user_message: str) -> list[dict]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system_prompt,
            tools=[PLAN_TOOL],
            tool_choice={"type": "tool", "name": "create_git_plan"},
            messages=[{"role": "user", "content": user_message}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "create_git_plan":
                return block.input.get("steps", [])

        raise RuntimeError("The AI did not return a structured Git plan.")
