from __future__ import annotations

import re

from app.schemas.repositories import LocalResolution, ReadAction


class LocalIntentMatcher:
    def resolve(self, message: str) -> LocalResolution:
        # Preserve the existing narrow read-only grammar. Trailing sentence
        # punctuation is normal conversational input, so remove only that
        # punctuation after normalising case and whitespace.
        original_text = " ".join(message.strip().split()).rstrip("?.!,")
        text = original_text.lower()

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

        conflicts_match = text in {
            "conflicts", "show conflicts", "list conflicts", "conflict status",
            "merge conflicts", "show merge conflicts",
        }
        if conflicts_match:
            return LocalResolution(
                matched=True,
                action=ReadAction.CONFLICTS,
                explanation="Resolved locally as conflict guidance.",
            )

        file_history_match = re.match(
            r"^(?:file\s+history|history|show\s+history\s+for|log\s+for)\s+(?P<path>.+)$",
            original_text,
            re.IGNORECASE,
        )
        if file_history_match:
            return LocalResolution(
                matched=True,
                action=ReadAction.FILE_HISTORY,
                params={"path": file_history_match.group("path")},
                explanation="Resolved locally as file history.",
            )

        blame_match = re.match(
            r"^(?:blame|show\s+blame\s+for|who\s+(?:changed|touched))\s+(?P<path>.+)$",
            original_text,
            re.IGNORECASE,
        )
        if blame_match:
            return LocalResolution(
                matched=True,
                action=ReadAction.BLAME,
                params={"path": blame_match.group("path")},
                explanation="Resolved locally as file blame.",
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

        if "remote" in text and any(token in text for token in ("show", "list", "what", "which")):
            return LocalResolution(
                matched=True,
                action=ReadAction.REMOTES,
                explanation="Resolved locally as remote listing.",
            )

        tag_show_match = re.match(
            r"^(?:show|inspect)\s+tag\s+(?P<tag>[A-Za-z0-9][A-Za-z0-9._/-]{0,254})$",
            original_text,
            re.IGNORECASE,
        )
        if tag_show_match:
            return LocalResolution(
                matched=True,
                action=ReadAction.TAG_SHOW,
                params={"tag_name": tag_show_match.group("tag")},
                explanation="Resolved locally as tag inspection.",
            )

        if text in {"tags", "tag list", "list tags", "show tags", "show tag list"}:
            return LocalResolution(
                matched=True,
                action=ReadAction.TAGS,
                explanation="Resolved locally as tag listing.",
            )

        if text in {"graph", "commit graph", "show graph", "show commit graph", "visual graph", "history graph"}:
            return LocalResolution(
                matched=True,
                action=ReadAction.GRAPH,
                explanation="Resolved locally as a visual commit graph.",
            )

        stash_show_match = re.search(r"\bstash@\{\d+\}", text)
        if stash_show_match and any(token in text for token in ("show", "inspect", "diff")):
            return LocalResolution(
                matched=True,
                action=ReadAction.STASH_SHOW,
                params={"stash_ref": stash_show_match.group(0)},
                explanation="Resolved locally as stash inspection.",
            )

        if text in {"stashes", "stash list", "list stashes", "show stashes", "show stash list"}:
            return LocalResolution(
                matched=True,
                action=ReadAction.STASHES,
                explanation="Resolved locally as stash listing.",
            )

        if "diff" in text or "difference" in text:
            scope = "all"
            if "staged" in text or "cached" in text:
                scope = "staged"
            elif "unstaged" in text or "working tree" in text:
                scope = "unstaged"
            return LocalResolution(
                matched=True,
                action=ReadAction.DIFF,
                params={"scope": scope},
                explanation="Resolved locally as a full patch diff.",
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
