from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_message: str) -> list[dict]:
        """Call the LLM and return a list of raw step dicts from the structured output."""
        ...

    @abstractmethod
    def complete_text(self, system_prompt: str, user_message: str, *, max_tokens: int = 120) -> str:
        """Call the LLM and return plain text."""
        ...

    def ping(self) -> None:
        """Send a minimal request to verify credentials and connectivity. Raises on failure."""
        self.complete_text("You are a test.", "Reply with the word ok.", max_tokens=4)
