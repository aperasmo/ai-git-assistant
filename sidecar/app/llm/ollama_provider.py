from __future__ import annotations

import json

import httpx

from app.llm.base import LLMProvider
from app.llm.prompt import PLAN_TOOL_OPENAI_FORMAT

_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_MODEL = "deepseek-r1:8b"


class OllamaProvider(LLMProvider):
    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self._model = model or _DEFAULT_MODEL
        self._base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")

    def ping(self) -> None:
        try:
            resp = httpx.get(f"{self._base_url}/api/tags", timeout=10.0)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Could not connect to Ollama at {self._base_url}. Make sure Ollama is running."
            ) from exc

    def complete(self, system_prompt: str, user_message: str) -> list[dict]:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "tools": [{"type": "function", "function": PLAN_TOOL_OPENAI_FORMAT}],
        }

        try:
            response = httpx.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=90.0,
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Could not connect to Ollama at {self._base_url}. "
                "Make sure Ollama is running."
            ) from exc

        data = response.json()
        message = data.get("message", {})
        tool_calls = message.get("tool_calls") or []

        for call in tool_calls:
            func = call.get("function", {})
            if func.get("name") == "create_git_plan":
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        pass
                if isinstance(args, dict):
                    return args.get("steps", [])

        # Fallback: try to parse JSON from the content field
        content = message.get("content", "")
        if content:
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "steps" in parsed:
                    return parsed["steps"]
            except (json.JSONDecodeError, TypeError):
                pass

        raise RuntimeError(
            f"Ollama ({self._model}) did not return a structured Git plan. "
            "Try a model that supports function/tool calling, such as deepseek-r1:8b or qwen3-coder:30b."
        )
