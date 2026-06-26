from __future__ import annotations

from app.schemas.repositories import RepositorySnapshot

SYSTEM_PROMPT = """\
You are an AI assistant embedded in a Git desktop application.
When the user types a natural language Git request, analyze it and call the create_git_plan tool.

SAFETY RULES — violating these is unacceptable:
- Never suggest force push (git push --force / git push -f)
- Never suggest git reset --hard
- Never suggest git clean -f
- Only use file paths that appear in the "Changed files" section of the user message
- Never use ".", "*", "all", or glob patterns as file paths
- Only use remotes that appear in the "Remotes" section

SUPPORTED OPERATIONS (use ONLY these):
- stage: Add specific files to the staging area (paths required)
- commit: Create a commit (commit_message required)
- push: Push a branch to a remote (remote and branch required; set set_upstream=true only if branch has no upstream)
- pull: Fast-forward pull from remote (remote and branch required)
- unstage: Remove files from the staging area (paths required)
- discard: Revert files to last committed state — DESTRUCTIVE (paths required)
- switch: Checkout an existing local branch (branch required)
- create_branch: Create and checkout a new branch from HEAD (branch required)
- stash: Save all staged and modified changes to the stash (commit_message optional for label)
- stash_pop: Restore the most recent stash entry
- delete_branch: Delete a local branch with safe-delete only (branch required)

For multi-step requests (e.g., "commit and push"), include all steps in the correct order.
For COMMIT steps that follow a STAGE step, do NOT repeat the paths in the COMMIT step.
The title field should be a short action label (e.g., "Stage 2 files", "Create commit", "Push to origin").
The detail field should explain what will happen.
The command_preview field should show the exact git command (e.g., "git add -- src/login.py").\
"""

# Anthropic tool schema (input_schema style)
PLAN_TOOL: dict = {
    "name": "create_git_plan",
    "description": "Create a structured Git action plan from the user's natural language request.",
    "input_schema": {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "description": "Ordered list of Git operations to perform",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": [
                                "stage", "commit", "push", "pull",
                                "unstage", "discard", "switch", "create_branch",
                                "stash", "stash_pop", "delete_branch",
                            ],
                        },
                        "title": {
                            "type": "string",
                            "description": "Short label shown in the plan UI",
                        },
                        "detail": {
                            "type": "string",
                            "description": "Explanation shown below the title",
                        },
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File paths — must be from the Changed files list only",
                        },
                        "commit_message": {"type": "string"},
                        "remote": {"type": "string"},
                        "branch": {"type": "string"},
                        "set_upstream": {"type": "boolean"},
                        "command_preview": {"type": "string"},
                    },
                    "required": ["kind", "title", "detail"],
                },
            },
        },
        "required": ["steps"],
    },
}

# OpenAI / Groq / Ollama function format
PLAN_TOOL_OPENAI_FORMAT: dict = {
    "name": "create_git_plan",
    "description": PLAN_TOOL["description"],
    "parameters": PLAN_TOOL["input_schema"],
}


def build_user_message(message: str, snapshot: RepositorySnapshot) -> str:
    lines = [
        f"User request: {message}",
        "",
        "Current repository state:",
        f"  Branch: {snapshot.branch or 'detached HEAD'}",
        f"  Ahead: {snapshot.ahead}, Behind: {snapshot.behind}",
    ]

    if snapshot.upstream_branch:
        lines.append(f"  Upstream: {snapshot.upstream_branch}")

    if snapshot.remote_names:
        lines.append(f"  Remotes: {', '.join(snapshot.remote_names)}")
    else:
        lines.append("  Remotes: none")

    lines.append("")
    lines.append("Changed files:")

    if snapshot.staged_changes:
        lines.append(f"  Staged ({len(snapshot.staged_changes)}):")
        for f in snapshot.staged_changes:
            lines.append(f"    {f.path}")

    if snapshot.modified_changes:
        lines.append(f"  Modified ({len(snapshot.modified_changes)}):")
        for f in snapshot.modified_changes:
            lines.append(f"    {f.path}")

    if snapshot.untracked_paths:
        lines.append(f"  Untracked ({len(snapshot.untracked_paths)}):")
        for f in snapshot.untracked_paths:
            lines.append(f"    {f.path}")

    if not snapshot.staged_changes and not snapshot.modified_changes and not snapshot.untracked_paths:
        lines.append("  (working tree is clean)")

    if snapshot.recent_commits:
        lines.append("")
        lines.append("Recent commits:")
        for c in snapshot.recent_commits[:3]:
            lines.append(f"  {c.short_hash}  {c.subject}")

    return "\n".join(lines)
