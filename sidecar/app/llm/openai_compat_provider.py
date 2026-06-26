from __future__ import annotations

import json

from app.llm.base import LLMProvider
from app.llm.prompt import PLAN_TOOL_OPENAI_FORMAT

_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-3.5-flash",
}
_BASE_URLS = {
    "openai": None,
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        provider: str = "openai",
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        try:
            import openai
        except ImportError as exc:
            raise RuntimeError(
                "The 'openai' package is not installed in the sidecar. "
                "Rebuild with: npm run sidecar:build"
            ) from exc

        self._model = model or _DEFAULT_MODELS.get(provider, "gpt-4o-mini")
        effective_base_url = base_url or _BASE_URLS.get(provider)

        self._client = openai.OpenAI(
            api_key=api_key,
            base_url=effective_base_url,
        )

    def complete(self, system_prompt: str, user_message: str) -> list[dict]:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            tools=[{"type": "function", "function": PLAN_TOOL_OPENAI_FORMAT}],
            tool_choice={"type": "function", "function": {"name": "create_git_plan"}},
        )

        message = response.choices[0].message
        if message.tool_calls:
            for call in message.tool_calls:
                if call.function.name == "create_git_plan":
                    args = call.function.arguments
                    if isinstance(args, str):
                        args = json.loads(args)
                    if isinstance(args, dict):
                        return args.get("steps", [])

        raise RuntimeError("The AI did not return a structured Git plan.")
