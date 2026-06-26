from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_message: str) -> list[dict]:
        """Call the LLM and return a list of raw step dicts from the structured output."""
        ...
