from __future__ import annotations

import re

from app.schemas.repositories import LocalResolution, ReadAction


class LocalIntentMatcher:
    def resolve(self, message: str) -> LocalResolution:
        # Preserve the existing narrow read-only grammar. Trailing sentence
        # punctuation is normal conversational input, so remove only that
        # punctuation after normalising case and whitespace.
        text = " ".join(message.lower().strip().split()).rstrip("?.!,")

        _STATUS_EXACT = {
            "status", "git status",
            "what changed", "what's changed", "whats changed",
            "what to commit", "what can i commit", "what's ready to commit",
            "whats ready to commit", "show status", "show me status",
        }
        _STATUS_CONTAINS = ("what to commit", "ready to commit", "staged changes")
        if text in _STATUS_EXACT or any(phrase in text for phrase in _STATUS_CONTAINS):
            return LocalResolution(
                matched=True,
                action=ReadAction.STATUS,
                explanation="Resolved locally as Git status.",
            )

        if "refresh remote" in text or "fetch" in text or "update remote status" in text:
            return LocalResolution(
                matched=True,
                action=ReadAction.FETCH,
                explanation="Resolved locally as an explicit remote refresh.",
            )

        if "branch" in text and any(token in text for token in ("show", "list", "what", "which")):
            return LocalResolution(
                matched=True,
                action=ReadAction.BRANCHES,
                explanation="Resolved locally as branch listing.",
            )

        if "diff" in text or "difference" in text:
            return LocalResolution(
                matched=True,
                action=ReadAction.DIFF,
                explanation="Resolved locally as a bounded diff summary.",
            )

        commits_match = re.search(r"(?:last|recent)\s+(\d{1,2})\s+(?:commits?|logs?)", text)
        if commits_match or text in {"log", "git log", "show log", "show logs", "show commits", "recent commits"}:
            limit = int(commits_match.group(1)) if commits_match else 5
            return LocalResolution(
                matched=True,
                action=ReadAction.LOG,
                params={"limit": max(1, min(limit, 50))},
                explanation="Resolved locally as recent commit history.",
            )

        return LocalResolution(
            matched=False,
            explanation="No supported local request matched this message.",
        )
