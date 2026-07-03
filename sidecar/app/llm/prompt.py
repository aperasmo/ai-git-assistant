from __future__ import annotations

from app.schemas.repositories import RepositorySnapshot

SYSTEM_PROMPT = """\
You are an AI assistant embedded in a Git desktop application.
Your only job: translate the user's natural language Git request into a precise, safe, \
step-by-step action plan by calling the create_git_plan tool.

━━━ UNDERSTANDING THE REQUEST ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"commit/push/stage all changes / everything / all files / all the changes"
  → stage EVERY path listed under "Changed files" (modified + untracked), then commit,
    then push if the user asked for it.

"commit [some filename]" / "stage [some filename]"
  → find the closest matching path(s) in the "Changed files" list and use only those.

"push" / "push to remote" / "push to origin"
  → push the current branch to the remote shown under "Remotes".
    Use set_upstream=true only when the branch has no upstream yet.

"commit and push …" / "push and commit …" / "stage then commit then push …"
  → multi-step plan: stage → commit → push (always in that order).

Commit message: extract it from the user's quoted string (single or double quotes).
  If no quotes, use the clearest phrase from the request as the message.

━━━ FILE PATH RULES (critical) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Use ONLY paths that appear verbatim in the "Changed files" section.
• NEVER use ".", "*", "all", glob patterns, or any invented path.
• "all changes / everything / all files" → include EVERY path from Changed files.
• User names a specific file → find the exact matching path from Changed files.
• List each file individually in the paths array — never batch with wildcards.

━━━ SAFETY RULES (never violate) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Never suggest force push (--force / -f).
• Never suggest git reset --hard or git clean -f.
• Only reference remotes that appear in the "Remotes" section.
• Only reference branches that exist unless creating a new one.

━━━ SUPPORTED STEP KINDS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

stage        — add files to staging area          (paths required)
commit       — create a commit                    (commit_message required)
push         — push branch to remote              (remote + branch required)
pull         — fast-forward pull                  (remote + branch required)
unstage      — remove files from staging          (paths required)
discard      — revert files to last commit — DESTRUCTIVE (paths required)
switch       — checkout an existing branch        (branch required)
create_branch — create + checkout a new branch   (branch required)
stash        — save staged+modified to stash      (commit_message optional)
stash_pop    — restore most recent stash entry
stash_apply  — apply a specific stash             (stash_ref required)
stash_drop   — delete a specific stash            (stash_ref required)
merge        — merge a local branch               (branch required)
merge_abort  — abort an in-progress merge
merge_commit — finish a resolved merge
delete_branch — safe-delete a local branch       (branch required)
create_tag   — create an annotated local tag      (tag_name + commit_message required)
delete_tag   — delete a local tag — DESTRUCTIVE   (tag_name required)
push_tag     — push one tag to one remote         (remote + tag_name required)

━━━ STEP FORMATTING ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

title          Short action label shown in the UI, e.g. "Stage 5 files"
detail         Plain English: what will happen and why
command_preview Exact git command, e.g. "git add -- src/App.tsx sidecar/main.py"

For a stage → commit sequence: do NOT repeat paths in the commit step.\
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
                                "stash", "stash_pop", "stash_apply", "stash_drop",
                                "merge", "merge_abort", "merge_commit", "delete_branch",
                                "create_tag", "delete_tag", "push_tag",
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
                            "description": "File paths — must be exact paths from the Changed files list only",
                        },
                        "commit_message": {"type": "string"},
                        "remote": {"type": "string"},
                        "branch": {"type": "string"},
                        "stash_ref": {"type": "string"},
                        "tag_name": {"type": "string"},
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


COMMIT_MESSAGE_SYSTEM_PROMPT = """\
You write concise Git commit messages.
Return exactly one commit subject line.
Use imperative mood, no trailing period, no quotes, no markdown.
Keep it 72 characters or fewer.
Do not mention file counts unless the change is only file movement or cleanup.
"""


CHANGE_SUMMARY_SYSTEM_PROMPT = """\
You are an AI Git reviewer inside a desktop Git client.
Summarize the selected working-tree changes for review before commit or PR creation.
Return only valid JSON with this exact shape:
{
  "branch_summary": "one short paragraph",
  "file_summaries": ["file: what changed"],
  "pr_title": "short PR title",
  "pr_body": "markdown body with summary and testing/checks if inferable",
  "commit_suggestions": [
    {"message": "imperative commit subject", "files": ["path"], "rationale": "why these files belong together"}
  ]
}
Rules:
- Use only the files and patch content provided.
- Do not invent tests, issues, branches, or files.
- Split mixed work into 1-5 logical commit suggestions.
- Commit messages must be 72 characters or fewer and use imperative mood.
"""


def build_commit_message_user_message(*, branch: str | None, diff_context: str) -> str:
    return "\n".join(
        [
            f"Current branch: {branch or 'detached HEAD'}",
            "",
            "Generate a commit message for this reviewed change:",
            "",
            diff_context,
        ]
    )


def build_change_summary_user_message(*, branch: str | None, diff_context: str) -> str:
    return "\n".join(
        [
            f"Current branch: {branch or 'detached HEAD'}",
            "",
            "Analyze these selected changes:",
            "",
            diff_context,
        ]
    )


def build_user_message(message: str, snapshot: RepositorySnapshot) -> str:
    lines = [
        f"User request: {message}",
        "",
        "Repository state:",
        f"  Branch:  {snapshot.branch or 'detached HEAD'}",
        f"  Ahead:   {snapshot.ahead}  Behind: {snapshot.behind}",
    ]

    if snapshot.upstream_branch:
        lines.append(f"  Upstream: {snapshot.upstream_branch}")

    if snapshot.remote_names:
        for name in snapshot.remote_names:
            url = (snapshot.remote_urls or {}).get(name, "")
            lines.append(f"  Remote:  {name}" + (f"  ({url})" if url else ""))
    else:
        lines.append("  Remotes: none")

    lines.append("")
    lines.append("Changed files:")

    has_changes = False

    if snapshot.staged_changes:
        has_changes = True
        lines.append(f"  Staged ({len(snapshot.staged_changes)}):")
        for f in snapshot.staged_changes:
            lines.append(f"    {f.path}")

    if snapshot.modified_changes:
        has_changes = True
        lines.append(f"  Modified ({len(snapshot.modified_changes)}):")
        for f in snapshot.modified_changes:
            lines.append(f"    {f.path}")

    if snapshot.untracked_paths:
        has_changes = True
        lines.append(f"  Untracked ({len(snapshot.untracked_paths)}):")
        for f in snapshot.untracked_paths:
            lines.append(f"    {f.path}")

    if not has_changes:
        lines.append("  (working tree is clean — nothing to stage or commit)")

    if snapshot.recent_commits:
        lines.append("")
        lines.append("Recent commits:")
        for c in snapshot.recent_commits[:3]:
            lines.append(f"  {c.short_hash}  {c.subject}")

    return "\n".join(lines)
