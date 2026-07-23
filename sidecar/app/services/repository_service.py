from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from threading import Lock
from time import monotonic
from uuid import uuid4

from app.config import Settings
from app.errors import GitCommandError, ValidationFailure
from app.git.client import GitClient, GitHttpAuth
from app.git.repository_inspector import RepositoryInspector
from app.intent.action_planner import LocalActionPlanner
from app.intent.local_matcher import LocalIntentMatcher
from app.schemas.repositories import (
    ActionExecutionResult,
    ActionPlanStep,
    AgentSessionActionResponse,
    AgentSessionComparisonResponse,
    AgentSessionResponse,
    ApplyConflictResolutionRequest,
    ApplyConflictResolutionResponse,
    BranchInfo,
    CancelActionPlanResponse,
    CommitMessageStyle,
    ConflictResolutionPreviewRequest,
    ConflictResolutionPreviewResponse,
    ConflictResolvedFile,
    DraftGitLabMergeRequestRequest,
    DraftGitLabMergeRequestResponse,
    DraftGitHubPullRequestRequest,
    DraftGitHubPullRequestResponse,
    DraftGitHubReleaseRequest,
    DraftGitHubReleaseResponse,
    GitHubDraftReleaseDetailsRequest,
    GitHubDraftReleaseDetailsResponse,
    GenerateChangeSummaryResponse,
    GeneratePullRequestDraftResponse,
    FolderClassificationResponse,
    GenerateCommitMessageResponse,
    LocalActionPlan,
    PlanKind,
    PlanRisk,
    PlanStepKind,
    PrivacyReceipt,
    PublishGitHubRepositoryRequest,
    PublishGitHubRepositoryResponse,
    ReadAction,
    ReadActionRequest,
    ReadActionResult,
    RecentCommit,
    ReleaseAssetUpload,
    RepositoryResponse,
    RepositorySnapshot,
    TeamContextTemplateResponse,
)
from app.services.repository_store import RepositoryStore
from app.services.github_release_service import GitHubReleaseClient, GitHubRepositoryRef, parse_github_remote_url
from app.services.gitlab_merge_request_service import (
    GitLabMergeRequestClient,
    GitLabRepositoryRef,
    parse_gitlab_remote_url,
)
from app.templates.team_context import DEFAULT_TEAM_CONTEXT_TEMPLATE

_logger = logging.getLogger("aiga.sidecar")

_PLAN_TTL_SECONDS = 5 * 60
_MAX_READ_OUTPUT_CHARS = 80_000
_MAX_COMMIT_MESSAGE_CONTEXT_CHARS = 14_000
_STASH_REF_PATTERN = re.compile(r"^stash@\{\d{1,3}\}$")
_TAG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_GITHUB_REPOSITORY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_GITHUB_HTTPS_REMOTE_PATTERN = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+?(?:\.git)?/?$")
_TEAM_CONTEXT_RELATIVE_PATH = Path(".ai-git-assistant") / "team-context.md"
_TEAM_CONTEXT_MAX_CHARS = 8_000
_CONFLICT_RESOLUTION_STEPS = {
    PlanStepKind.STAGE,
    PlanStepKind.MERGE_ABORT,
    PlanStepKind.MERGE_COMMIT,
}
_READ_ONLY_REQUEST_PATTERN = re.compile(
    r"^\s*(?:git\s+)?(?:"
    r"status|diff|log|logs|history|blame|graph|branches?|remotes?|stashes?|tags?|conflicts?|"
    r"review\s+status|pr\s+status|pull\s+request\s+status|mr\s+status|merge\s+request\s+status|"
    r"ci\s+status|checks"
    r")\b",
    re.IGNORECASE,
)
_AGENT_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,119}$")
_PR_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")


@dataclass(frozen=True)
class PendingWritePlan:
    plan: LocalActionPlan
    snapshot_fingerprint: str
    expires_at: float


@dataclass(frozen=True)
class AiDiffContext:
    content: str
    files: list[str]
    context_items: list[str]
    truncated: bool


class RepositoryService:
    def __init__(
        self,
        store: RepositoryStore,
        inspector: RepositoryInspector,
        matcher: LocalIntentMatcher,
        settings: Settings,
        settings_service=None,
    ) -> None:
        self.store = store
        self.inspector = inspector
        self.matcher = matcher
        self.planner = LocalActionPlanner(matcher)
        self.settings = settings
        self.settings_service = settings_service
        self._llm_router = None
        if settings_service is not None:
            from app.llm.router import LLMRouter
            self._llm_router = LLMRouter(settings_service)
        self._github_release_client_factory = GitHubReleaseClient
        self._gitlab_merge_request_client_factory = GitLabMergeRequestClient
        self._pending_plans: dict[str, PendingWritePlan] = {}
        self._pending_plans_lock = Lock()

    def classify_selected_folder(
        self,
        selected_path: str,
    ) -> FolderClassificationResponse:
        classification = self.inspector.classify_selected_folder(selected_path)

        # The inspector owns filesystem and Git probing. The service maps that
        # internal result into the stable response contract used by the API/UI.
        return FolderClassificationResponse(
            kind=classification.kind,
            selected_path=str(classification.selected_path),
            repository_root=(
                str(classification.repository_root)
                if classification.repository_root is not None
                else None
            ),
            can_initialise=classification.can_initialise,
            message=classification.message,
        )

    def initialise_and_register(self, selected_path: str) -> RepositoryResponse:
        # Re-check immediately before writing. A folder can change after the UI
        # classified it, so only a known plain folder may be initialised.
        classification = self.inspector.classify_selected_folder(selected_path)

        if classification.kind != "initialisation_required":
            raise ValidationFailure(
                "This folder cannot be initialised because it is no longer a plain "
                "non-Git folder."
            )

        client = GitClient(classification.selected_path)
        client.initialise_repository(self.settings.initial_branch)

        # Register through the existing strict validation path so newly created
        # repositories receive the same safety checks as existing repositories.
        return self.register(str(classification.selected_path))

    def remove_repository(self, repository_id: str) -> None:
        self.store.get(repository_id)  # raises NotFoundError if missing
        self.store.remove(repository_id)

    def clone_repository(self, url: str, parent_path: str, folder_name: str | None = None) -> RepositoryResponse:
        from pathlib import Path as _Path
        parent = _Path(parent_path)
        if not parent.is_dir():
            raise ValidationFailure("The selected parent folder does not exist.")

        if not folder_name:
            name = url.rstrip("/").rsplit("/", 1)[-1]
            folder_name = name[:-4] if name.endswith(".git") else name or "repository"

        target = parent / folder_name
        if target.exists():
            raise ValidationFailure(f"A folder named '{folder_name}' already exists at this location.")

        client = GitClient(parent)
        try:
            client.clone(url, target)
        except GitCommandError as exc:
            msg = exc.message.lower()
            if any(k in msg for k in ("authentication failed", "403", "401", "permission denied", "invalid username")):
                raise GitCommandError(
                    "Authentication failed. Make sure Git Credential Manager is set up for HTTPS, "
                    "or use an SSH URL (git@github.com:user/repo.git) with your SSH key configured."
                ) from exc
            if any(k in msg for k in ("repository not found", "404", "not found")):
                raise GitCommandError(
                    "Repository not found. Check the URL and make sure you have access."
                ) from exc
            if "could not read from remote" in msg:
                raise GitCommandError(
                    "Could not connect to the remote. Check your URL and network connection."
                ) from exc
            raise

        return self.register(str(target))

    def create_agent_session(
        self,
        repository_id: str,
        *,
        task: str,
        branch_name: str | None = None,
        base_branch: str | None = None,
    ) -> AgentSessionResponse:
        repository = self.store.get(repository_id)
        canonical_path = self.store.canonical_path(repository_id)
        snapshot = self.snapshot(repository_id)
        if snapshot.write_blocked_reason:
            raise ValidationFailure(snapshot.write_blocked_reason)
        if snapshot.conflicts:
            raise ValidationFailure("Resolve merge conflicts before creating an agent worktree.")
        base_ref = base_branch or snapshot.branch
        if not base_ref:
            raise ValidationFailure("A named branch is required before creating an agent worktree.")

        session_id = str(uuid4())
        suffix = session_id.split("-", 1)[0]
        slug = self._agent_slug(task)
        branch = branch_name or f"agent/{slug}-{suffix}"
        self._validate_agent_branch(branch)

        worktree_root = self._agent_worktree_root(repository_id)
        worktree_root.mkdir(parents=True, exist_ok=True)
        worktree_path = worktree_root / f"{slug}-{suffix}"
        if worktree_path.exists():
            raise ValidationFailure("The generated agent worktree path already exists. Try again.")

        GitClient(canonical_path).worktree_add(worktree_path, branch, base_ref)
        stored = self.store.create_agent_session(
            repository_id=repository.id,
            task=task.strip(),
            branch_name=branch,
            base_branch=base_ref,
            worktree_path=worktree_path,
        )
        return self._with_agent_runtime(stored)

    def list_agent_sessions(self, repository_id: str) -> list[AgentSessionResponse]:
        self.store.get(repository_id)
        return [self._with_agent_runtime(session) for session in self.store.list_agent_sessions(repository_id)]

    def compare_agent_session(self, repository_id: str, session_id: str) -> AgentSessionComparisonResponse:
        session = self._with_agent_runtime(self.store.get_agent_session(repository_id, session_id))
        if session.status == "cleaned" or not Path(session.worktree_path).exists():
            return AgentSessionComparisonResponse(
                session=session,
                title=f"Agent session: {session.task}",
                summary="Worktree files are no longer available.",
                content=(
                    f"Task: {session.task}\n"
                    f"Branch: {session.branch_name}\n"
                    f"Base: {session.base_branch}\n"
                    f"Worktree: {session.worktree_path}\n\n"
                    "This session record is retained, but the worktree files have been cleaned up."
                ),
            )
        client = GitClient(Path(session.worktree_path))
        commits = client.log_range_oneline(f"{session.base_branch}..HEAD").strip()
        stat = client.compare_stat(session.base_branch, "HEAD").strip()
        files = client.compare_name_status(session.base_branch, "HEAD").strip()
        status = client.short_status().strip()
        sections = [
            f"Task: {session.task}",
            f"Branch: {session.branch_name}",
            f"Base: {session.base_branch}",
            f"Worktree: {session.worktree_path}",
            "",
            "Commits ahead:",
            commits or "(no commits yet)",
            "",
            "Changed files:",
            files or "(no committed file changes yet)",
            "",
            "Diff stat:",
            stat or "(no committed diff yet)",
            "",
            "Working tree status:",
            status or "(clean)",
        ]
        return AgentSessionComparisonResponse(
            session=session,
            title=f"Agent session: {session.task}",
            summary=f"{session.commits_ahead} commit(s), {session.changed_file_count} working-tree change(s)",
            content="\n".join(sections),
        )

    def merge_agent_session(self, repository_id: str, session_id: str) -> AgentSessionActionResponse:
        session = self._with_agent_runtime(self.store.get_agent_session(repository_id, session_id))
        if session.status != "active":
            raise ValidationFailure("Only active agent sessions can be merged.")
        if session.commits_ahead <= 0:
            raise ValidationFailure("The agent branch has no commits to merge.")

        snapshot = self.snapshot(repository_id)
        changed_count = len(snapshot.staged_changes) + len(snapshot.modified_changes) + len(snapshot.untracked_paths)
        if changed_count or snapshot.conflicts:
            raise ValidationFailure("The main repository must be clean before merging an agent session.")

        client = GitClient(self.store.canonical_path(repository_id))
        result = client.merge_branch_no_ff(
            session.branch_name,
            f"Merge agent session: {session.task}",
        )
        updated = self._with_agent_runtime(
            self.store.update_agent_session_status(repository_id, session_id, "merged")
        )
        return AgentSessionActionResponse(
            session=updated,
            title="Agent session merged",
            summary=f"Merged {session.branch_name} into the selected repository.",
            content=(result.stdout or result.stderr or "Merge completed.").strip(),
        )

    def abandon_agent_session(self, repository_id: str, session_id: str) -> AgentSessionActionResponse:
        session = self._with_agent_runtime(self.store.get_agent_session(repository_id, session_id))
        if session.status not in {"active", "error"}:
            raise ValidationFailure("Only active or errored agent sessions can be abandoned.")
        root_client = GitClient(self.store.canonical_path(repository_id))
        if Path(session.worktree_path).exists():
            root_client.worktree_remove(Path(session.worktree_path), force=True)
        root_client.branch_delete_force(session.branch_name)
        updated = self._with_agent_runtime(
            self.store.update_agent_session_status(repository_id, session_id, "abandoned")
        )
        return AgentSessionActionResponse(
            session=updated,
            title="Agent session abandoned",
            summary=f"Removed worktree and branch {session.branch_name}.",
            content="The isolated agent worktree was removed and its branch was deleted.",
        )

    def cleanup_agent_session(self, repository_id: str, session_id: str) -> AgentSessionActionResponse:
        session = self._with_agent_runtime(self.store.get_agent_session(repository_id, session_id))
        if session.status == "active":
            raise ValidationFailure("Active sessions must be merged or abandoned before cleanup.")
        path = Path(session.worktree_path)
        if path.exists():
            GitClient(self.store.canonical_path(repository_id)).worktree_remove(path, force=True)
        updated = self._with_agent_runtime(
            self.store.update_agent_session_status(repository_id, session_id, "cleaned")
        )
        return AgentSessionActionResponse(
            session=updated,
            title="Agent session cleaned up",
            summary=f"Removed stored worktree files for {session.branch_name}.",
            content="The session record is retained, but its worktree files are cleaned up.",
        )

    def register(self, selected_path: str) -> RepositoryResponse:
        canonical_path = self.inspector.canonicalise_and_validate(selected_path)
        provisional = self.store.upsert(canonical_path, current_branch=None)
        snapshot = self.snapshot(provisional.id)
        return self.store.upsert(canonical_path, current_branch=snapshot.branch)

    def list(self) -> list[RepositoryResponse]:
        return self.store.list()

    def snapshot(self, repository_id: str) -> RepositorySnapshot:
        repository = self.store.get(repository_id)
        canonical_path = self.store.canonical_path(repository_id)
        inspection = self.inspector.inspect(
            repository_id,
            canonical_path,
            remote_last_refreshed_at=repository.last_remote_refresh_at,
        )
        snapshot = inspection.snapshot.model_copy(
            update={"recent_commits": self._recent_commits(canonical_path)}
        )
        self.store.update_inspection(repository_id, branch=snapshot.branch)
        return snapshot

    def plan_local_request(self, repository_id: str, message: str) -> LocalActionPlan:
        snapshot = self.snapshot(repository_id)
        plan = self.planner.plan(repository_id, message, snapshot)

        if plan.matched:
            if not plan.requires_confirmation:
                return plan
            plan_id = str(uuid4())
            persisted_plan = self._with_plan_metadata(
                plan.model_copy(update={"plan_id": plan_id}),
                snapshot=snapshot,
                privacy_receipt=self._local_privacy_receipt("Plan Git write action"),
            )
            self._store_pending_plan(
                PendingWritePlan(
                    plan=persisted_plan,
                    snapshot_fingerprint=snapshot.fingerprint,
                    expires_at=monotonic() + _PLAN_TTL_SECONDS,
                )
            )
            return persisted_plan

        # Local planner didn't match — try LLM fallback if configured
        if self._looks_like_read_only_request(message):
            return plan.model_copy(update={
                "explanation": (
                    "This looks like a read-only Git request, but it did not match a supported local "
                    "read command. Rephrase it as 'show log', 'last 5 commits', 'show diff', or "
                    "'what changed?' so the app can run a safe read action."
                )
            })

        repository = self.store.get(repository_id)
        if self._llm_router is None or not repository.external_llm_allowed:
            return plan

        try:
            from app.llm.router import LLMNotConfiguredError
            validated_steps = self._llm_router.plan(message, snapshot)
        except LLMNotConfiguredError:
            return plan
        except Exception as exc:
            _logger.exception("LLM fallback failed")
            return plan.model_copy(update={
                "explanation": (
                    f"No local match found. The AI assistant was attempted but encountered an error: "
                    f"{str(exc)[:120]}"
                )
            })

        plan_id = str(uuid4())
        llm_privacy = self._llm_privacy_receipt(
            purpose="Generate Git action plan",
            files=self._changed_paths(snapshot),
            context_items=[
                "User request",
                "Branch, upstream, ahead/behind counts",
                "Remote names and URLs",
                "Changed file names",
                "Recent commit subjects",
            ],
            exact_context=(
                "The AI plan fallback receives the typed request plus repository metadata "
                "and changed file names only. It does not receive file contents or diffs."
            ),
        )
        llm_plan = self._with_plan_metadata(
            LocalActionPlan(
            matched=True,
            repository_id=repository_id,
            message=message,
            plan_kind=PlanKind.WRITE,
            requires_confirmation=True,
            plan_id=plan_id,
            steps=validated_steps,
            explanation=(
                "AI-generated plan — review all steps carefully before approving. "
                "The AI interprets your request but you remain in control."
            ),
            source="llm",
            ),
            snapshot=snapshot,
            privacy_receipt=llm_privacy,
        )
        self._store_pending_plan(
            PendingWritePlan(
                plan=llm_plan,
                snapshot_fingerprint=snapshot.fingerprint,
                expires_at=monotonic() + _PLAN_TTL_SECONDS,
            )
        )
        return llm_plan

    @staticmethod
    def _looks_like_read_only_request(message: str) -> bool:
        text = " ".join(message.strip().split()).lower()
        if not text:
            return False
        if _READ_ONLY_REQUEST_PATTERN.search(text):
            return True
        return bool(
            re.search(
                r"\b(?:show|list|view|inspect|read)\s+(?:the\s+)?"
                r"(?:log|logs|commits|status|diff|branches|remotes|stashes|tags|conflicts)\b",
                text,
            )
        )

    def _agent_worktree_root(self, repository_id: str) -> Path:
        return self.settings.database_path.parent / "agent-worktrees" / repository_id

    @staticmethod
    def _agent_slug(value: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
        return (slug or "task")[:48].strip("-") or "task"

    @staticmethod
    def _validate_agent_branch(branch_name: str) -> None:
        if not _AGENT_BRANCH_PATTERN.match(branch_name):
            raise ValidationFailure(
                "Agent branch names may contain letters, numbers, dots, underscores, slashes, and hyphens."
            )
        if branch_name.startswith("/") or branch_name.endswith("/") or ".." in branch_name:
            raise ValidationFailure("Agent branch name is not valid.")

    @staticmethod
    def _with_agent_runtime(session: AgentSessionResponse) -> AgentSessionResponse:
        path = Path(session.worktree_path)
        if not path.exists() or session.status in {"abandoned", "cleaned"}:
            return session.model_copy(update={
                "changed_file_count": 0,
                "commits_ahead": 0,
                "last_commit": None,
            })
        client = GitClient(path)
        status_lines = [line for line in client.short_status().splitlines() if line.strip()]
        commits_ahead = client.rev_list_count(f"{session.base_branch}..HEAD")
        last_commit = client.last_commit_oneline() or None
        return session.model_copy(update={
            "changed_file_count": len(status_lines),
            "commits_ahead": commits_ahead,
            "last_commit": last_commit,
        })

    def set_external_llm_allowed(self, repository_id: str, allowed: bool) -> RepositoryResponse:
        self.store.update_external_llm_allowed(repository_id, allowed)
        return self.store.get(repository_id)

    _GITIGNORE_SECTION_MARKER = "# -- AI GIT ASSISTANT --"
    _GITIGNORE_HEADER = (
        "############################\n"
        "# -- AI GIT ASSISTANT --\n"
        "############################\n"
    )

    def add_to_gitignore(self, repository_id: str, paths: list[str]) -> None:
        root = self.store.canonical_path(repository_id)
        gitignore = root / ".gitignore"
        existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
        existing_lines = {line.strip() for line in existing.splitlines() if line.strip()}
        new_lines = []
        seen = set(existing_lines)
        for path in paths:
            line = path.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            new_lines.append(line)
        if not new_lines:
            return
        has_our_section = self._GITIGNORE_SECTION_MARKER in existing
        with gitignore.open("a", encoding="utf-8") as fh:
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            if not has_our_section:
                fh.write(self._GITIGNORE_HEADER)
            for line in new_lines:
                fh.write(f"{line}\n")

    def create_team_context_template(self, repository_id: str) -> TeamContextTemplateResponse:
        root = self.store.canonical_path(repository_id)
        context_dir = root / _TEAM_CONTEXT_RELATIVE_PATH.parent
        context_path = root / _TEAM_CONTEXT_RELATIVE_PATH

        if context_path.exists():
            raise ValidationFailure(
                "Team context already exists. Open .ai-git-assistant/team-context.md and edit it for this repository."
            )

        try:
            context_dir.mkdir(parents=True, exist_ok=True)
            context_path.write_text(
                DEFAULT_TEAM_CONTEXT_TEMPLATE.rstrip() + "\n",
                encoding="utf-8",
                newline="\n",
            )
        except OSError as exc:
            raise ValidationFailure(f"Could not create team context: {exc}") from exc

        snapshot = self.snapshot(repository_id)
        return TeamContextTemplateResponse(
            title="Team context template added",
            summary="A repo-local AI guidance file was created.",
            content=(
                "Created .ai-git-assistant/team-context.md.\n\n"
                "Review and edit this file so AI Git Assistant follows this repository's commit, PR/MR, "
                "validation, documentation, and release conventions. Keep it free of secrets."
            ),
            snapshot=snapshot,
        )

    def submit_wizard_plan(
        self,
        repository_id: str,
        steps: list[ActionPlanStep],
    ) -> str:
        """Store a pre-built wizard plan, bypassing the intent matcher."""
        snapshot = self.snapshot(repository_id)
        plan_id = str(uuid4())
        plan = self._with_plan_metadata(
            LocalActionPlan(
            matched=True,
            repository_id=repository_id,
            message="wizard",
            plan_kind=PlanKind.WRITE,
            requires_confirmation=True,
            plan_id=plan_id,
            read_action=None,
            read_params={},
            steps=steps,
            explanation="Submitted via wizard.",
            source="local",
            ),
            snapshot=snapshot,
            privacy_receipt=self._local_privacy_receipt("Submit wizard Git plan"),
        )
        self._store_pending_plan(
            PendingWritePlan(
                plan=plan,
                snapshot_fingerprint=snapshot.fingerprint,
                expires_at=monotonic() + _PLAN_TTL_SECONDS,
            )
        )
        return plan_id

    def generate_commit_message(
        self,
        repository_id: str,
        paths: list[str],
        style: CommitMessageStyle = "detailed",
    ) -> GenerateCommitMessageResponse:
        repository = self.store.get(repository_id)
        if not repository.external_llm_allowed:
            raise ValidationFailure(
                "AI commit messages are disabled for this repository. Enable AI for this repo first."
            )
        if self._llm_router is None:
            raise ValidationFailure("No AI provider is configured. Open Settings to add one.")

        snapshot = self.snapshot(repository_id)
        canonical_path = self.store.canonical_path(repository_id)
        selected_paths = self._normalise_commit_message_paths(paths, snapshot)
        diff_context = self._build_ai_diff_context(
            canonical_path,
            selected_paths,
            snapshot,
        )
        if not diff_context.content.strip():
            raise ValidationFailure("There is no diff context available for the selected files.")

        draft = self._llm_router.commit_message(
            branch=snapshot.branch,
            diff_context=diff_context.content,
            style=style,
        )
        receipt = self._llm_privacy_receipt(
            purpose="Generate commit message",
            files=diff_context.files,
            context_items=diff_context.context_items,
            exact_context=diff_context.content,
            truncated=diff_context.truncated,
        )
        return GenerateCommitMessageResponse(
            message=draft.message,
            subject=draft.subject,
            body=draft.body,
            warning=draft.warning,
            style=style,
            confidence=draft.confidence,
            detected_scope=draft.detected_scope or [],
            alternatives=draft.alternatives or [],
            context_summary=(
                f"Generated one {style.replace('_', ' ')} message from {len(selected_paths)} selected file"
                f"{'s' if len(selected_paths) != 1 else ''}."
            ),
            privacy_receipt=receipt,
        )

    def generate_change_summary(
        self,
        repository_id: str,
        paths: list[str],
    ) -> GenerateChangeSummaryResponse:
        repository = self.store.get(repository_id)
        if not repository.external_llm_allowed:
            raise ValidationFailure(
                "AI change summaries are disabled for this repository. Enable AI for this repo first."
            )
        if self._llm_router is None:
            raise ValidationFailure("No AI provider is configured. Open Settings to add one.")

        snapshot = self.snapshot(repository_id)
        canonical_path = self.store.canonical_path(repository_id)
        selected_paths = self._normalise_commit_message_paths(paths, snapshot)
        diff_context = self._build_ai_diff_context(
            canonical_path,
            selected_paths,
            snapshot,
        )
        if not diff_context.content.strip():
            raise ValidationFailure("There is no diff context available for the selected files.")

        context_summary = (
            f"Analyzed {len(selected_paths)} selected file"
            f"{'s' if len(selected_paths) != 1 else ''}."
        )
        response = self._llm_router.change_summary(
            branch=snapshot.branch,
            diff_context=diff_context.content,
            context_summary=context_summary,
        )
        receipt = self._llm_privacy_receipt(
            purpose="Analyze changes and suggest commits",
            files=diff_context.files,
            context_items=diff_context.context_items,
            exact_context=diff_context.content,
            truncated=diff_context.truncated,
        )
        return response.model_copy(update={"privacy_receipt": receipt})

    def preview_conflict_resolution(
        self,
        repository_id: str,
        request: ConflictResolutionPreviewRequest,
    ) -> ConflictResolutionPreviewResponse:
        repository = self.store.get(repository_id)
        canonical_path = self.store.canonical_path(repository_id)
        snapshot = self.snapshot(repository_id)
        conflict_paths = {item.path for item in snapshot.conflicts}
        if not conflict_paths:
            raise ValidationFailure("No conflicted files are available to resolve.")

        requested_paths = request.paths or sorted(conflict_paths)
        invalid = [path for path in requested_paths if path not in conflict_paths]
        if invalid:
            raise ValidationFailure(
                "Only currently conflicted files can be resolved: " + ", ".join(invalid[:5])
            )

        resolved_files: list[ConflictResolvedFile] = []
        total_chars = 0
        for raw_path in requested_paths:
            path = self._normalise_requested_path(raw_path)
            file_path = canonical_path / path
            if not file_path.is_file():
                raise ValidationFailure(f"Conflicted file '{raw_path}' was not found.")
            current = file_path.read_text(encoding="utf-8", errors="replace")
            total_chars += len(current)
            if total_chars > 60_000:
                raise ValidationFailure(
                    "Conflict preview is too large for one automated pass. Resolve fewer files at a time."
                )

            has_markers = self._has_conflict_markers(current)
            if not has_markers:
                resolved = current
                count = 0
                summary = (
                    "No conflict markers were found. This file appears to be manually resolved "
                    "and will be marked resolved."
                )
            elif request.strategy == "ai":
                if not repository.external_llm_allowed:
                    raise ValidationFailure(
                        "Enable Repository AI context before using AI conflict resolution for this repository."
                    )
                if self._llm_router is None:
                    raise ValidationFailure("No AI provider is configured for conflict resolution.")
                resolved, count, summary = self._resolve_conflict_with_ai(raw_path, current)
            else:
                resolved, count = self._resolve_conflict_markers(current, request.strategy)
                summary = (
                    "Kept local conflict sections."
                    if request.strategy == "ours"
                    else "Kept incoming remote conflict sections."
                )

            if self._has_conflict_markers(resolved):
                raise ValidationFailure(
                    f"Resolved content for '{raw_path}' still contains conflict markers."
                )
            resolved_files.append(
                ConflictResolvedFile(
                    path=raw_path,
                    content=resolved,
                    conflict_count=count,
                    summary=summary,
                )
            )

        strategy_label = {
            "ours": "keep local version",
            "theirs": "keep remote version",
            "ai": "AI proposal",
        }[request.strategy]
        content_lines = [
            f"Strategy: {strategy_label}",
            "",
            "Resolved files:",
            *[
                f"- {item.path} ({item.conflict_count} conflict block{'s' if item.conflict_count != 1 else ''})"
                for item in resolved_files
            ],
            "",
            "Preview:",
        ]
        for item in resolved_files:
            content_lines.extend(
                [
                    "",
                    f"--- {item.path}",
                    item.summary,
                    self._preview_resolved_content(item.content),
                ]
            )

        privacy_receipt = None
        if request.strategy == "ai":
            privacy_receipt = self._llm_privacy_receipt(
                purpose="AI conflict resolution preview",
                files=[item.path for item in resolved_files],
                context_items=["conflicted file contents"],
                exact_context="Conflicted file contents were sent to the configured AI provider for a resolution proposal.",
                truncated=False,
            )

        return ConflictResolutionPreviewResponse(
            strategy=request.strategy,
            title="Conflict resolution preview",
            summary=f"Preview prepared for {len(resolved_files)} conflicted file(s). Nothing has been written yet.",
            content=self._bound_read_output("\n".join(content_lines)),
            resolved_files=resolved_files,
            privacy_receipt=privacy_receipt,
            snapshot=snapshot,
        )

    def apply_conflict_resolution(
        self,
        repository_id: str,
        request: ApplyConflictResolutionRequest,
    ) -> ApplyConflictResolutionResponse:
        canonical_path = self.store.canonical_path(repository_id)
        snapshot = self.snapshot(repository_id)
        conflict_paths = {item.path for item in snapshot.conflicts}
        if not conflict_paths:
            raise ValidationFailure("No conflicted files are available to resolve.")

        paths: list[str] = []
        for item in request.resolved_files:
            if item.path not in conflict_paths:
                raise ValidationFailure(f"'{item.path}' is no longer a conflicted file.")
            if self._has_conflict_markers(item.content):
                raise ValidationFailure(f"Resolved content for '{item.path}' still contains conflict markers.")
            path = self._normalise_requested_path(item.path)
            file_path = canonical_path / path
            if not file_path.is_file():
                raise ValidationFailure(f"Conflicted file '{item.path}' was not found.")
            file_path.write_text(item.content, encoding="utf-8")
            paths.append(item.path)

        GitClient(canonical_path).stage_paths(paths)
        next_snapshot = self.snapshot(repository_id)
        content = "\n".join(
            [
                f"Applied {request.strategy} conflict resolution.",
                "",
                "Resolved files:",
                *[f"- {path}" for path in paths],
                "",
                "Next step: run continue merge from the app.",
            ]
        )
        return ApplyConflictResolutionResponse(
            title="Conflict resolution applied",
            summary=f"{len(paths)} file(s) were written and marked resolved.",
            content=content,
            snapshot=next_snapshot,
        )

    def generate_pull_request_draft(
        self,
        repository_id: str,
        base_branch: str,
    ) -> GeneratePullRequestDraftResponse:
        repository = self.store.get(repository_id)
        if not repository.external_llm_allowed:
            raise ValidationFailure(
                "AI pull request drafts are disabled for this repository. Enable AI for this repo first."
            )
        if self._llm_router is None:
            raise ValidationFailure("No AI provider is configured. Open Settings to add one.")

        snapshot = self.snapshot(repository_id)
        head_branch = snapshot.branch
        base_branch = base_branch.strip()
        self._validate_pr_branch_name(base_branch)
        if not head_branch:
            raise ValidationFailure("Pull request drafts require a named branch, not detached HEAD.")
        self._validate_pr_branch_name(head_branch)
        if head_branch == base_branch:
            raise ValidationFailure("Choose a base branch different from the current branch.")
        if snapshot.write_blocked_reason or snapshot.conflicts:
            raise ValidationFailure("Resolve repository conflicts before drafting pull request text.")

        canonical_path = self.store.canonical_path(repository_id)
        diff_context = self._build_ai_pull_request_context(canonical_path, base_branch, head_branch, snapshot)
        if not diff_context.content.strip():
            raise ValidationFailure("There is no branch comparison context available for the pull request.")

        context_summary = f"Generated PR draft from branch comparison {base_branch}...{head_branch}."
        response = self._llm_router.change_summary(
            branch=head_branch,
            diff_context=diff_context.content,
            context_summary=context_summary,
        )
        receipt = self._llm_privacy_receipt(
            purpose="Generate pull request title and body",
            files=diff_context.files,
            context_items=diff_context.context_items,
            exact_context=diff_context.content,
            truncated=diff_context.truncated,
        )
        checklist = self._extract_pr_checklist(response.pr_body)
        return GeneratePullRequestDraftResponse(
            title=response.pr_title,
            body=response.pr_body,
            checklist=checklist,
            branch_summary=response.branch_summary,
            file_summaries=response.file_summaries,
            context_summary=context_summary,
            privacy_receipt=receipt,
        )

    def publish_github_repository(
        self,
        repository_id: str,
        request: PublishGitHubRepositoryRequest,
    ) -> PublishGitHubRepositoryResponse:
        if self.settings_service is None:
            raise ValidationFailure("GitHub settings are unavailable.")

        token = self.settings_service.get_raw_github_token()
        if not token:
            raise ValidationFailure(
                "No GitHub token is configured. Open Settings and add a token that can create repositories."
            )

        repository_name = request.repository_name.strip()
        if not _GITHUB_REPOSITORY_NAME_PATTERN.match(repository_name):
            raise ValidationFailure("Use a GitHub repository name with only letters, numbers, dots, dashes, or underscores.")

        snapshot = self.snapshot(repository_id)
        if snapshot.remote_names:
            raise ValidationFailure(
                "This repository already has a remote. Use Pull latest, Commit & push, or Connect remote for existing remotes."
            )
        if snapshot.write_blocked_reason or snapshot.conflicts:
            raise ValidationFailure("Resolve repository conflicts before publishing this repository.")

        canonical_path = self.store.canonical_path(repository_id)
        client = GitClient(canonical_path)
        changed_paths = self._changed_paths_from_snapshot(snapshot)
        selected_paths = self._normalise_publish_paths(request.paths, changed_paths)
        completed_steps: list[str] = []

        try:
            if selected_paths:
                client.stage_paths(selected_paths)
                completed_steps.append("Stage files")
                staged_snapshot = self.snapshot(repository_id)
                if not staged_snapshot.staged_changes:
                    raise ValidationFailure("There are no staged changes available for the first publish commit.")
                client.commit(request.commit_message.strip())
                completed_steps.append("Commit")
            elif not snapshot.head_commit:
                raise ValidationFailure("Select files for the first commit before publishing this repository.")

            branch_snapshot = self.snapshot(repository_id)
            current_branch = branch_snapshot.branch or "main"
            if current_branch != "main":
                client.rename_branch("main")
                completed_steps.append("Rename branch to main")
            target_branch = "main"

            github = self._github_release_client_factory(token)
            created = github.create_repository(
                name=repository_name,
                description=request.description.strip(),
                private=request.private,
            )
            completed_steps.append("Create GitHub repository")

            remote_url = created.clone_url or f"{created.html_url}.git"
            if not remote_url:
                raise ValidationFailure("GitHub created the repository but did not return a clone URL.")
            client.remote_add("origin", remote_url)
            completed_steps.append("Add origin remote")
            client.push_with_set_upstream(
                "origin",
                target_branch,
                http_auth=GitHttpAuth(username="x-access-token", password=token),
            )
            completed_steps.append("Push with upstream")
        except GitCommandError as exc:
            msg = exc.message
            if "author identity unknown" in msg.lower():
                raise GitCommandError(
                    "Git cannot create the commit because author identity is not configured. "
                    "Open Settings, add your Git author name and email, then try Publish to GitHub again."
                ) from exc
            if completed_steps:
                raise GitCommandError(
                    f"Completed before the failure: {', '.join(completed_steps)}. Git then reported: {msg}"
                ) from exc
            raise

        latest_snapshot = self.snapshot(repository_id)
        content_lines = [
            f"Repository: {created.slug}",
            f"Visibility: {'private' if created.private else 'public'}",
            f"GitHub URL: {created.html_url}",
            f"Remote: origin -> {remote_url}",
            f"Branch: {target_branch}",
        ]
        if selected_paths:
            content_lines.extend(
                [
                    "",
                    f"Committed {len(selected_paths)} file{'s' if len(selected_paths) != 1 else ''}:",
                    *[f"- {path}" for path in selected_paths],
                ]
            )
        else:
            content_lines.extend(["", "No new commit was needed; existing commits were published."])
        content_lines.extend(["", f"Ahead: {latest_snapshot.ahead}", f"Behind: {latest_snapshot.behind}"])

        return PublishGitHubRepositoryResponse(
            repository=created.slug,
            repository_url=created.html_url,
            remote_url=remote_url,
            branch=target_branch,
            title="Repository Published to GitHub",
            summary=f"Created {created.slug}, connected origin, and pushed main with upstream tracking.",
            content="\n".join(content_lines),
            snapshot=latest_snapshot,
        )

    def draft_github_release(
        self,
        repository_id: str,
        request: DraftGitHubReleaseRequest,
    ) -> DraftGitHubReleaseResponse:
        if self.settings_service is None:
            raise ValidationFailure("GitHub settings are unavailable.")

        token = self.settings_service.get_raw_github_token()
        if not token:
            raise ValidationFailure("No GitHub token is configured. Open Settings and add a token with Contents write access.")

        snapshot = self.snapshot(repository_id)
        repository_ref = self._github_repository_from_snapshot(snapshot)
        self._validate_tag_name(request.tag_name)

        asset_path_values = [path for path in request.asset_paths if path.strip()]
        if request.asset_path and request.asset_path.strip():
            asset_path_values.insert(0, request.asset_path)

        asset_paths: list[Path] = []
        seen_assets: set[str] = set()
        for asset_path_value in asset_path_values:
            asset_path = Path(asset_path_value).expanduser()
            if not asset_path.is_file():
                raise ValidationFailure("The selected release asset does not exist or is not a file.")
            resolved = str(asset_path.resolve())
            if resolved in seen_assets:
                continue
            seen_assets.add(resolved)
            asset_paths.append(asset_path)

        client = self._github_release_client_factory(token)
        result = client.create_draft_release(
            repository=repository_ref,
            tag_name=request.tag_name,
            title=request.title.strip(),
            body=request.body.strip(),
            target_commitish=snapshot.head_commit or snapshot.branch,
            prerelease=request.prerelease,
            asset_paths=asset_paths,
            asset_path=asset_paths[0] if asset_paths else None,
        )
        latest_snapshot = self.snapshot(repository_id)
        action_label = "updated" if result.action == "updated" else "created"
        uploaded_count = sum(1 for asset in result.assets if asset.status == "uploaded")
        existing_count = sum(1 for asset in result.assets if asset.status == "already_exists")

        content_lines = [
            f"Repository: {repository_ref.slug}",
            f"Tag: {result.tag_name}",
            f"GitHub tag ref: {'created' if result.remote_tag_created else 'already available'}",
            f"Release: {result.release_url}",
            "Draft: yes",
            f"Action: {action_label}",
            f"Prerelease: {'yes' if request.prerelease else 'no'}",
        ]
        if result.assets:
            content_lines.extend(
                [
                    "",
                    f"Assets selected: {len(result.assets)}",
                    f"Assets uploaded: {uploaded_count}",
                    f"Already on draft: {existing_count}",
                ]
            )
            for asset in result.assets:
                content_lines.extend(
                    [
                        f"- {asset.name} ({asset.status.replace('_', ' ')})",
                        f"  URL: {asset.url or '(not returned)'}",
                        f"  SHA-256: {asset.sha256}",
                    ]
                )

        return DraftGitHubReleaseResponse(
            tag_name=result.tag_name,
            repository=repository_ref.slug,
            release_url=result.release_url,
            action=result.action,
            asset_url=result.asset_url,
            asset_name=result.asset_name,
            asset_sha256=result.asset_sha256,
            assets=[
                ReleaseAssetUpload(
                    name=asset.name,
                    url=asset.url,
                    sha256=asset.sha256,
                    status=asset.status,
                )
                for asset in result.assets
            ],
            title=f"GitHub Draft Release {action_label.title()}",
            summary=(
                f"A draft GitHub release was {action_label}"
                + (f"; {uploaded_count} asset(s) uploaded" if uploaded_count else "")
                + (f"; {existing_count} asset(s) already existed" if existing_count else "")
                + "."
            ),
            content="\n".join(content_lines),
            snapshot=latest_snapshot,
        )

    def get_github_draft_release(
        self,
        repository_id: str,
        request: GitHubDraftReleaseDetailsRequest,
    ) -> GitHubDraftReleaseDetailsResponse:
        if self.settings_service is None:
            raise ValidationFailure("GitHub settings are unavailable.")

        token = self.settings_service.get_raw_github_token()
        if not token:
            raise ValidationFailure("No GitHub token is configured. Open Settings and add a token with Contents read access.")

        snapshot = self.snapshot(repository_id)
        repository_ref = self._github_repository_from_snapshot(snapshot)
        self._validate_tag_name(request.tag_name)

        client = self._github_release_client_factory(token)
        details = client.get_draft_release(
            repository=repository_ref,
            tag_name=request.tag_name,
        )
        return GitHubDraftReleaseDetailsResponse(
            tag_name=details.tag_name,
            repository=repository_ref.slug,
            release_url=details.release_url,
            title=details.title,
            body=details.body,
            assets=[
                ReleaseAssetUpload(
                    name=asset.name,
                    url=asset.url,
                    sha256=asset.sha256,
                    status=asset.status,
                )
                for asset in details.assets
            ],
        )

    def draft_github_pull_request(
        self,
        repository_id: str,
        request: DraftGitHubPullRequestRequest,
    ) -> DraftGitHubPullRequestResponse:
        if self.settings_service is None:
            raise ValidationFailure("GitHub settings are unavailable.")

        token = self.settings_service.get_raw_github_token()
        if not token:
            raise ValidationFailure(
                "No GitHub token is configured. Open Settings and add a token with Contents read/write "
                "and Pull requests read/write access."
            )

        snapshot = self.snapshot(repository_id)
        repository_ref = self._github_repository_from_snapshot(snapshot)
        head_branch = snapshot.branch
        base_branch = request.base_branch.strip()
        self._validate_pr_branch_name(base_branch)

        if not head_branch:
            raise ValidationFailure("Draft pull requests require a named branch, not detached HEAD.")
        self._validate_pr_branch_name(head_branch)
        if head_branch == base_branch:
            raise ValidationFailure("Choose a base branch different from the current branch.")
        if snapshot.write_blocked_reason or snapshot.conflicts:
            raise ValidationFailure("Resolve repository conflicts before drafting a pull request.")
        if snapshot.ahead > 0:
            raise ValidationFailure(
                "The current branch has local commits that are not pushed yet. Push first, then draft the pull request."
            )

        canonical_path = self.store.canonical_path(repository_id)
        client = GitClient(canonical_path)
        github_remote = self._github_remote_name_from_snapshot(snapshot)
        if not client.remote_branch_exists(
            github_remote,
            head_branch,
            http_auth=self._git_http_auth_for_remote(snapshot, github_remote),
        ):
            raise ValidationFailure(
                f"GitHub cannot see branch '{head_branch}' on remote '{github_remote}'. Push the branch first."
            )

        commits = client.log_range_oneline(f"{base_branch}..{head_branch}").strip()
        changed_files = client.compare_name_status(base_branch, head_branch).strip()
        diff_stat = client.compare_stat(base_branch, head_branch).strip()

        client_api = self._github_release_client_factory(token)
        result = client_api.create_draft_pull_request(
            repository=repository_ref,
            title=request.title.strip(),
            body=request.body.strip(),
            head=head_branch,
            base=base_branch,
        )
        latest_snapshot = self.snapshot(repository_id)
        content_lines = [
            f"Repository: {repository_ref.slug}",
            f"Draft PR: {result.pull_request_url}",
            f"Number: #{result.number}",
            f"Base: {base_branch}",
            f"Head: {head_branch}",
            "Draft: yes",
            "",
            "Commits:",
            commits or "(GitHub accepted the PR, but no local commit range was available.)",
            "",
            "Changed files:",
            changed_files or "(No local file list available.)",
            "",
            "Diff stat:",
            diff_stat or "(No local diff stat available.)",
        ]

        return DraftGitHubPullRequestResponse(
            repository=repository_ref.slug,
            pull_request_url=result.pull_request_url,
            number=result.number,
            base_branch=base_branch,
            head_branch=head_branch,
            title="GitHub Draft Pull Request Created",
            summary=f"Draft PR #{result.number} was created from {head_branch} into {base_branch}.",
            content="\n".join(content_lines),
            snapshot=latest_snapshot,
        )

    def draft_gitlab_merge_request(
        self,
        repository_id: str,
        request: DraftGitLabMergeRequestRequest,
    ) -> DraftGitLabMergeRequestResponse:
        if self.settings_service is None:
            raise ValidationFailure("GitLab settings are unavailable.")

        token = self.settings_service.get_raw_gitlab_token()
        if not token:
            raise ValidationFailure(
                "No GitLab token is configured. Open Settings and add a token with api scope."
            )

        snapshot = self.snapshot(repository_id)
        repository_ref = self._gitlab_repository_from_snapshot(snapshot)
        head_branch = snapshot.branch
        base_branch = request.base_branch.strip()
        self._validate_pr_branch_name(base_branch)

        if not head_branch:
            raise ValidationFailure("Draft merge requests require a named branch, not detached HEAD.")
        self._validate_pr_branch_name(head_branch)
        if head_branch == base_branch:
            raise ValidationFailure("Choose a base branch different from the current branch.")
        if snapshot.write_blocked_reason or snapshot.conflicts:
            raise ValidationFailure("Resolve repository conflicts before drafting a merge request.")
        if snapshot.ahead > 0:
            raise ValidationFailure(
                "The current branch has local commits that are not pushed yet. Push first, then draft the merge request."
            )

        canonical_path = self.store.canonical_path(repository_id)
        client = GitClient(canonical_path)
        gitlab_remote = self._gitlab_remote_name_from_snapshot(snapshot)
        if not client.remote_branch_exists(gitlab_remote, head_branch):
            raise ValidationFailure(
                f"GitLab cannot see branch '{head_branch}' on remote '{gitlab_remote}'. Push the branch first."
            )

        commits = client.log_range_oneline(f"{base_branch}..{head_branch}").strip()
        changed_files = client.compare_name_status(base_branch, head_branch).strip()
        diff_stat = client.compare_stat(base_branch, head_branch).strip()

        gitlab_settings = self.settings_service.get_gitlab_settings()
        base_url = gitlab_settings.base_url or f"https://{repository_ref.host}"
        client_api = self._gitlab_merge_request_client_factory(token, base_url=base_url)
        result = client_api.create_draft_merge_request(
            repository=repository_ref,
            title=request.title.strip(),
            body=request.body.strip(),
            source_branch=head_branch,
            target_branch=base_branch,
        )
        latest_snapshot = self.snapshot(repository_id)
        content_lines = [
            f"Repository: {repository_ref.slug}",
            f"Draft MR: {result.merge_request_url}",
            f"Number: !{result.number}",
            f"Base: {base_branch}",
            f"Head: {head_branch}",
            "Draft: yes",
            "",
            "Commits:",
            commits or "(GitLab accepted the MR, but no local commit range was available.)",
            "",
            "Changed files:",
            changed_files or "(No local file list available.)",
            "",
            "Diff stat:",
            diff_stat or "(No local diff stat available.)",
        ]

        return DraftGitLabMergeRequestResponse(
            repository=repository_ref.slug,
            merge_request_url=result.merge_request_url,
            number=result.number,
            base_branch=base_branch,
            head_branch=head_branch,
            title="GitLab Draft Merge Request Created",
            summary=f"Draft MR !{result.number} was created from {head_branch} into {base_branch}.",
            content="\n".join(content_lines),
            snapshot=latest_snapshot,
        )

    def execute_action_plan(
        self,
        repository_id: str,
        plan_id: str,
    ) -> ActionExecutionResult:
        pending = self._take_pending_plan(repository_id, plan_id)
        plan = pending.plan

        if not plan.requires_confirmation:
            raise ValidationFailure("This plan does not require execution.")

        current_snapshot = self.snapshot(repository_id)
        if current_snapshot.fingerprint != pending.snapshot_fingerprint:
            raise ValidationFailure(
                "Repository state changed after this plan was prepared. Request a new plan and review it again."
            )
        if current_snapshot.write_blocked_reason and not self._is_conflict_resolution_plan(plan):
            raise ValidationFailure(current_snapshot.write_blocked_reason)

        canonical_path = self.store.canonical_path(repository_id)
        client = GitClient(canonical_path)
        completed_steps: list[str] = []

        try:
            for step in plan.steps:
                if step.kind is PlanStepKind.STAGE:
                    if current_snapshot.write_blocked_reason and current_snapshot.conflicts:
                        conflict_paths = {item.path for item in current_snapshot.conflicts}
                        invalid = [path for path in step.paths if path not in conflict_paths]
                        if invalid:
                            raise ValidationFailure(
                                "During conflict resolution, only conflicted files can be staged."
                            )
                    client.stage_paths(step.paths)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.COMMIT:
                    post_stage_snapshot = self.snapshot(repository_id)
                    if not post_stage_snapshot.staged_changes:
                        raise ValidationFailure("There are no staged changes available to commit.")
                    if not step.commit_message:
                        raise ValidationFailure("The reviewed plan has no commit message.")
                    client.commit(step.commit_message)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.PUSH:
                    self._validate_push_step_against_current_repository(repository_id, step)
                    if not step.remote or not step.branch:
                        raise ValidationFailure("The reviewed plan has no validated push target.")
                    http_auth = self._git_http_auth_for_remote(current_snapshot, step.remote)
                    if step.set_upstream:
                        client.push_with_set_upstream(step.remote, step.branch, http_auth=http_auth)
                    else:
                        client.push_current_head(step.remote, step.branch, http_auth=http_auth)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.PULL:
                    client.pull_ff_only(http_auth=self._git_http_auth_for_upstream(current_snapshot))
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.SET_UPSTREAM:
                    self._validate_set_upstream_step_against_current_repository(repository_id, step)
                    if not step.remote or not step.branch:
                        raise ValidationFailure("The reviewed plan has no validated upstream target.")
                    client.set_upstream(step.remote, step.branch)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.UNSTAGE:
                    client.restore_staged(step.paths)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.DISCARD:
                    client.restore_working_tree(step.paths)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.SWITCH:
                    if not step.branch:
                        raise ValidationFailure("The reviewed plan has no target branch.")
                    client.switch_branch(step.branch)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.CREATE_BRANCH:
                    if not step.branch:
                        raise ValidationFailure("The reviewed plan has no branch name.")
                    client.create_and_switch_branch(step.branch)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.STASH:
                    client.stash_push(step.commit_message)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.STASH_POP:
                    client.stash_pop()
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.STASH_APPLY:
                    if not step.stash_ref:
                        raise ValidationFailure("The reviewed plan has no stash reference.")
                    self._validate_stash_ref(step.stash_ref)
                    client.stash_apply(step.stash_ref)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.STASH_DROP:
                    if not step.stash_ref:
                        raise ValidationFailure("The reviewed plan has no stash reference.")
                    self._validate_stash_ref(step.stash_ref)
                    client.stash_drop(step.stash_ref)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.MERGE:
                    if not step.branch:
                        raise ValidationFailure("The reviewed plan has no merge branch.")
                    client.merge_branch(step.branch)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.MERGE_ABORT:
                    client.merge_abort()
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.MERGE_COMMIT:
                    latest = self.snapshot(repository_id)
                    if latest.conflicts:
                        raise ValidationFailure("Resolve all conflicted files before continuing the merge.")
                    if "merge" not in (latest.write_blocked_reason or "").lower():
                        raise ValidationFailure("No merge appears to be in progress.")
                    client.merge_commit()
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.CREATE_TAG:
                    if not step.tag_name:
                        raise ValidationFailure("The reviewed plan has no tag name.")
                    if not step.commit_message:
                        raise ValidationFailure("The reviewed plan has no tag message.")
                    self._validate_tag_name(step.tag_name)
                    client.create_annotated_tag(step.tag_name, step.commit_message)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.DELETE_TAG:
                    if not step.tag_name:
                        raise ValidationFailure("The reviewed plan has no tag name.")
                    self._validate_tag_name(step.tag_name)
                    client.delete_tag(step.tag_name)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.PUSH_TAG:
                    if not step.tag_name:
                        raise ValidationFailure("The reviewed plan has no tag name.")
                    if not step.remote:
                        raise ValidationFailure("The reviewed plan has no remote.")
                    self._validate_tag_name(step.tag_name)
                    self._validate_tag_push_step_against_current_repository(repository_id, step)
                    client.push_tag(
                        step.remote,
                        step.tag_name,
                        http_auth=self._git_http_auth_for_remote(current_snapshot, step.remote),
                    )
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.DELETE_BRANCH:
                    if not step.branch:
                        raise ValidationFailure("The reviewed plan has no branch name.")
                    client.delete_branch(step.branch)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.ADD_REMOTE:
                    if not step.remote or not step.remote_url:
                        raise ValidationFailure("The reviewed plan is missing remote name or URL.")
                    client.remote_add(step.remote, step.remote_url)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.RENAME_BRANCH:
                    if not step.branch:
                        raise ValidationFailure("The reviewed plan has no branch name.")
                    client.rename_branch(step.branch)
                    completed_steps.append(step.title)
                    continue

                raise ValidationFailure("The reviewed plan contains an unsupported Git action.")
        except GitCommandError as exc:
            msg = exc.message
            if "would be overwritten by checkout" in msg or "would be overwritten by merge" in msg:
                raise GitCommandError(
                    "Cannot switch branches — you have local changes that would be overwritten. "
                    "Use 'Stash changes' to save your work first, then switch branches."
                ) from exc
            if "src refspec" in msg and "does not match any" in msg:
                raise GitCommandError(
                    "Cannot push — this repository has no commits yet. "
                    "Use 'Stage & commit' to create your first commit, then connect the remote."
                ) from exc
            if "already exists" in msg and "branch" in msg.lower():
                raise GitCommandError(
                    f"A branch named 'main' already exists. {msg}"
                ) from exc
            if "automatic merge failed" in msg.lower() or "fix conflicts" in msg.lower():
                raise GitCommandError(
                    "Merge stopped with conflicts. Use 'show conflicts' to inspect the conflicted files, "
                    "edit them in your workspace, stage the resolved files, then run 'continue merge' or 'abort merge'."
                ) from exc
            if completed_steps:
                completed = ", ".join(completed_steps)
                raise GitCommandError(
                    f"Completed before the failure: {completed}. Git then reported: {msg}"
                ) from exc
            raise

        snapshot = self.snapshot(repository_id)
        return self._render_execution_result(plan, snapshot)

    def cancel_action_plan(
        self,
        repository_id: str,
        plan_id: str,
    ) -> CancelActionPlanResponse:
        with self._pending_plans_lock:
            self._prune_expired_plans_locked()
            pending = self._pending_plans.get(plan_id)
            if pending is None or pending.plan.repository_id != repository_id:
                return CancelActionPlanResponse(cancelled=False)
            del self._pending_plans[plan_id]

        return CancelActionPlanResponse(cancelled=True)

    def run_read_action(
        self,
        repository_id: str,
        request: ReadActionRequest,
    ) -> ReadActionResult:
        canonical_path = self.store.canonical_path(repository_id)
        client = GitClient(canonical_path)

        if request.action is ReadAction.STATUS:
            snapshot = self.snapshot(repository_id)
            content = self._render_status(snapshot)
            return ReadActionResult(
                action=request.action,
                title="Git Status",
                summary="Live repository state was inspected locally.",
                content=content,
                snapshot=snapshot,
            )

        if request.action is ReadAction.LOG:
            limit = self._bounded_limit(request.params.get("limit", 5))
            snapshot = self.snapshot(repository_id)
            content = self._render_log(client.log(limit))
            return ReadActionResult(
                action=request.action,
                title=f"Last {limit} commits",
                summary="Commit history was read locally and bounded to the requested limit.",
                content=content or "No commits found.",
                snapshot=snapshot,
            )

        if request.action is ReadAction.DIFF:
            scope = str(request.params.get("scope", "all"))
            if scope not in {"all", "staged", "unstaged"}:
                raise ValidationFailure("Diff scope must be all, staged, or unstaged.")
            snapshot = self.snapshot(repository_id)
            content = self._bound_read_output(client.diff_patch(scope).strip())
            return ReadActionResult(
                action=request.action,
                title="Patch Diff",
                summary="Full patch diff was read locally with external diff tools disabled.",
                content=content or "No differences in the selected scope.",
                content_kind="diff",
                snapshot=snapshot,
            )

        if request.action is ReadAction.GRAPH:
            limit = self._bounded_limit(request.params.get("limit", 40))
            snapshot = self.snapshot(repository_id)
            content = self._bound_read_output(client.commit_graph(limit).strip())
            return ReadActionResult(
                action=request.action,
                title="Commit Graph",
                summary="Commit graph was read locally across branches.",
                content=content or "No commits found.",
                content_kind="graph",
                snapshot=snapshot,
            )

        if request.action is ReadAction.BRANCHES:
            snapshot = self.snapshot(repository_id)
            content = self._render_branches(client.branch_list())
            return ReadActionResult(
                action=request.action,
                title="Local Branches",
                summary="Local branch names were read without switching branches.",
                content=content or "No local branches found.",
                snapshot=snapshot,
            )

        if request.action is ReadAction.REMOTES:
            snapshot = self.snapshot(repository_id)
            content = self._render_remotes(client.remote_verbose())
            return ReadActionResult(
                action=request.action,
                title="Remotes",
                summary="Configured Git remotes were read locally.",
                content=content or "No remotes configured.",
                snapshot=snapshot,
            )

        if request.action is ReadAction.TAGS:
            snapshot = self.snapshot(repository_id)
            content = self._render_tags(client.tag_list())
            return ReadActionResult(
                action=request.action,
                title="Tags",
                summary="Local Git tags were read without modifying the repository.",
                content=content or "No tags found.",
                snapshot=snapshot,
            )

        if request.action is ReadAction.TAG_SHOW:
            tag_name = self._normalise_requested_tag(str(request.params.get("tag_name", "")))
            snapshot = self.snapshot(repository_id)
            content = self._bound_read_output(client.tag_show(tag_name).strip())
            return ReadActionResult(
                action=request.action,
                title=f"Tag: {tag_name}",
                summary="The selected tag was inspected locally.",
                content=content or f"No output for tag {tag_name}.",
                content_kind="diff",
                snapshot=snapshot,
            )

        if request.action is ReadAction.FILE_HISTORY:
            path = self._normalise_requested_path(str(request.params.get("path", "")))
            limit = self._bounded_limit(request.params.get("limit", 30))
            snapshot = self.snapshot(repository_id)
            content = self._render_log(client.file_history(path, limit))
            return ReadActionResult(
                action=request.action,
                title=f"History: {path}",
                summary="File history was read locally with rename following enabled.",
                content=content or f"No commits found for {path}.",
                snapshot=snapshot,
            )

        if request.action is ReadAction.BLAME:
            path = self._normalise_requested_path(str(request.params.get("path", "")))
            snapshot = self.snapshot(repository_id)
            content = self._bound_read_output(client.blame(path).strip())
            return ReadActionResult(
                action=request.action,
                title=f"Blame: {path}",
                summary="Line authorship was read locally.",
                content=content or f"No blame output for {path}.",
                snapshot=snapshot,
            )

        if request.action is ReadAction.CONFLICTS:
            snapshot = self.snapshot(repository_id)
            content = self._render_conflicts(canonical_path, snapshot)
            return ReadActionResult(
                action=request.action,
                title="Conflict Guidance",
                summary="Conflicted files and next steps were inspected locally.",
                content=content,
                content_kind="diff",
                snapshot=snapshot,
            )

        if request.action is ReadAction.STASHES:
            snapshot = self.snapshot(repository_id)
            content = self._render_stashes(client.stash_list())
            return ReadActionResult(
                action=request.action,
                title="Stash List",
                summary="Local stash entries were read without modifying the working tree.",
                content=content or "No stash entries found.",
                snapshot=snapshot,
            )

        if request.action is ReadAction.STASH_SHOW:
            stash_ref = str(request.params.get("stash_ref", "stash@{0}")).lower()
            self._validate_stash_ref(stash_ref)
            snapshot = self.snapshot(repository_id)
            content = self._bound_read_output(client.stash_show_patch(stash_ref).strip())
            return ReadActionResult(
                action=request.action,
                title=f"Inspect {stash_ref}",
                summary="The selected stash was inspected locally without applying it.",
                content=content or f"{stash_ref} has no patch output.",
                content_kind="diff",
                snapshot=snapshot,
            )

        if request.action is ReadAction.FETCH:
            pre_snapshot = self.snapshot(repository_id)
            client.fetch_prune(http_auth=self._git_http_auth_for_upstream(pre_snapshot))
            refreshed_at = datetime.now(UTC).isoformat()
            self.store.update_inspection(
                repository_id,
                branch=pre_snapshot.branch,
                remote_last_refreshed_at=refreshed_at,
                update_remote_refresh=True,
            )
            snapshot = self.snapshot(repository_id)
            return ReadActionResult(
                action=request.action,
                title="Remote Status Refreshed",
                summary=(
                    "Remote tracking references were refreshed explicitly with git fetch --prune."
                ),
                content=(
                    f"Remote refresh completed.\nAhead: {snapshot.ahead}\nBehind: {snapshot.behind}"
                ),
                snapshot=snapshot,
            )

        if request.action is ReadAction.REVIEW_STATUS:
            snapshot = self.snapshot(repository_id)
            content = self._render_review_status(repository_id, snapshot)
            return ReadActionResult(
                action=request.action,
                title="Review Status",
                summary="Current branch PR/MR status was read from the remote provider.",
                content=content,
                snapshot=snapshot,
            )

        raise ValidationFailure("Unsupported read action.")

    def _render_review_status(
        self,
        repository_id: str,
        snapshot: RepositorySnapshot,
    ) -> str:
        if not snapshot.branch:
            raise ValidationFailure("Review status requires a named branch, not detached HEAD.")
        if self.settings_service is None:
            raise ValidationFailure("Provider settings are unavailable.")

        providers = {provider.provider for provider in snapshot.remote_providers}
        if "github" in providers:
            return self._render_github_review_status(snapshot)
        if "gitlab" in providers:
            return self._render_gitlab_review_status(snapshot)
        if not snapshot.remote_providers:
            return (
                "No remote provider detected.\n\n"
                "Review status needs an open GitHub pull request or GitLab merge request for the current branch."
            )
        return (
            f"Detected remote provider: {self._remote_provider_summary(snapshot)}\n\n"
            "Review status currently supports GitHub pull requests and GitLab merge requests. "
            "Bitbucket and Azure DevOps review integrations are planned."
        )

    def _render_github_review_status(self, snapshot: RepositorySnapshot) -> str:
        token = self.settings_service.get_raw_github_token()
        if not token:
            raise ValidationFailure(
                "No GitHub token is configured. Open Settings and add a token with Pull requests read access."
            )
        repository_ref = self._github_repository_from_snapshot(snapshot)
        client_api = self._github_release_client_factory(token)
        status = client_api.get_pull_request_status(
            repository=repository_ref,
            head_branch=snapshot.branch or "",
        )
        if status is None:
            return (
                f"Provider: GitHub\nRepository: {repository_ref.slug}\nBranch: {snapshot.branch}\n\n"
                "No open pull request was found for the current branch."
            )
        return self._format_change_request_status(
            provider="GitHub",
            repository=repository_ref.slug,
            number_prefix="#",
            number=status.number,
            url=status.url,
            title=status.title,
            state=status.state,
            draft=status.draft,
            base_branch=status.base_branch,
            head_branch=status.head_branch,
            head_sha=status.head_sha,
            ci_status=status.ci_status,
            review_summary=status.review_summary,
            review_count=status.review_count,
            comment_count=status.comment_count,
            latest_comments=list(status.latest_comments),
        )

    def _render_gitlab_review_status(self, snapshot: RepositorySnapshot) -> str:
        token = self.settings_service.get_raw_gitlab_token()
        if not token:
            raise ValidationFailure(
                "No GitLab token is configured. Open Settings and add a token with api scope."
            )
        repository_ref = self._gitlab_repository_from_snapshot(snapshot)
        gitlab_settings = self.settings_service.get_gitlab_settings()
        base_url = gitlab_settings.base_url or f"https://{repository_ref.host}"
        client_api = self._gitlab_merge_request_client_factory(token, base_url=base_url)
        status = client_api.get_merge_request_status(
            repository=repository_ref,
            source_branch=snapshot.branch or "",
        )
        if status is None:
            return (
                f"Provider: GitLab\nRepository: {repository_ref.slug}\nBranch: {snapshot.branch}\n\n"
                "No open merge request was found for the current branch."
            )
        return self._format_change_request_status(
            provider="GitLab",
            repository=repository_ref.slug,
            number_prefix="!",
            number=status.number,
            url=status.url,
            title=status.title,
            state=status.state,
            draft=status.draft,
            base_branch=status.base_branch,
            head_branch=status.head_branch,
            head_sha=status.head_sha,
            ci_status=status.ci_status,
            review_summary=status.review_summary,
            review_count=status.review_count,
            comment_count=status.comment_count,
            latest_comments=list(status.latest_comments),
        )

    @staticmethod
    def _format_change_request_status(
        *,
        provider: str,
        repository: str,
        number_prefix: str,
        number: int,
        url: str,
        title: str,
        state: str,
        draft: bool,
        base_branch: str,
        head_branch: str,
        head_sha: str,
        ci_status: str,
        review_summary: str,
        review_count: int,
        comment_count: int,
        latest_comments: list[str],
    ) -> str:
        short_sha = head_sha[:12] if head_sha else "unknown"
        lines = [
            f"Provider: {provider}",
            f"Repository: {repository}",
            f"Change request: {number_prefix}{number} {title}",
            f"URL: {url or '(not returned)'}",
            f"State: {state}",
            f"Draft: {'yes' if draft else 'no'}",
            f"Base: {base_branch or 'unknown'}",
            f"Head: {head_branch or 'unknown'}",
            f"Head SHA: {short_sha}",
            "",
            f"CI/check status: {ci_status or 'unknown'}",
            f"Reviews: {review_summary} ({review_count} event{'s' if review_count != 1 else ''})",
            f"Comments: {comment_count}",
        ]
        if latest_comments:
            lines.extend(["", "Latest comments:"])
            lines.extend(f"- {comment}" for comment in latest_comments[:5])
        return "\n".join(lines)

    @staticmethod
    def _github_repository_from_snapshot(snapshot: RepositorySnapshot) -> GitHubRepositoryRef:
        if not snapshot.remote_urls:
            raise ValidationFailure(
                "GitHub platform actions are not available because this repository has no remote. "
                "Local Git features still work."
            )

        ordered_urls: list[str] = []
        origin_url = snapshot.remote_urls.get("origin")
        if origin_url:
            ordered_urls.append(origin_url)
        ordered_urls.extend(
            url for name, url in snapshot.remote_urls.items()
            if name != "origin"
        )

        for remote_url in ordered_urls:
            repository_ref = parse_github_remote_url(remote_url)
            if repository_ref is not None:
                return repository_ref

        detected = RepositoryService._remote_provider_summary(snapshot)
        raise ValidationFailure(
            "GitHub platform actions are not available for this repository. "
            f"Detected remote provider: {detected}. "
            "You can still use status, commits, branches, push, pull, fetch, tags, stash, merge, "
            "and AI summaries. Use Draft PR for GitLab merge requests; Bitbucket and Azure DevOps "
            "platform integrations are planned."
        )

    @staticmethod
    def _github_remote_name_from_snapshot(snapshot: RepositorySnapshot) -> str:
        for provider in snapshot.remote_providers:
            if provider.provider == "github":
                return provider.remote
        for name, remote_url in snapshot.remote_urls.items():
            if parse_github_remote_url(remote_url) is not None:
                return name
        raise ValidationFailure("No GitHub remote was found for this repository.")

    def _git_http_auth_for_remote(
        self,
        snapshot: RepositorySnapshot,
        remote: str | None,
    ) -> GitHttpAuth | None:
        if not remote:
            return None
        remote_url = (snapshot.remote_urls.get(remote) or "").strip()
        if not _GITHUB_HTTPS_REMOTE_PATTERN.match(remote_url):
            return None
        if self.settings_service is None:
            return None
        token = self.settings_service.get_raw_github_token()
        if not token:
            return None
        return GitHttpAuth(username="x-access-token", password=token)

    def _git_http_auth_for_upstream(self, snapshot: RepositorySnapshot) -> GitHttpAuth | None:
        return self._git_http_auth_for_remote(snapshot, snapshot.upstream_remote)

    @staticmethod
    def _gitlab_repository_from_snapshot(snapshot: RepositorySnapshot) -> GitLabRepositoryRef:
        if not snapshot.remote_urls:
            raise ValidationFailure(
                "GitLab platform actions are not available because this repository has no remote. "
                "Local Git features still work."
            )

        ordered_urls: list[str] = []
        origin_url = snapshot.remote_urls.get("origin")
        if origin_url:
            ordered_urls.append(origin_url)
        ordered_urls.extend(
            url for name, url in snapshot.remote_urls.items()
            if name != "origin"
        )

        for remote_url in ordered_urls:
            repository_ref = parse_gitlab_remote_url(remote_url)
            if repository_ref is not None:
                return repository_ref

        detected = RepositoryService._remote_provider_summary(snapshot)
        raise ValidationFailure(
            "GitLab platform actions are not available for this repository. "
            f"Detected remote provider: {detected}. "
            "You can still use status, commits, branches, push, pull, fetch, tags, stash, merge, "
            "and AI summaries. GitHub draft pull requests are available for GitHub repositories; "
            "Bitbucket and Azure DevOps platform integrations are planned."
        )

    @staticmethod
    def _gitlab_remote_name_from_snapshot(snapshot: RepositorySnapshot) -> str:
        for provider in snapshot.remote_providers:
            if provider.provider == "gitlab":
                return provider.remote
        for name, remote_url in snapshot.remote_urls.items():
            if parse_gitlab_remote_url(remote_url) is not None:
                return name
        raise ValidationFailure("No GitLab remote was found for this repository.")

    @staticmethod
    def _remote_provider_summary(snapshot: RepositorySnapshot) -> str:
        if not snapshot.remote_providers:
            return "Local only"

        parts = []
        for provider in snapshot.remote_providers:
            host = f" ({provider.host})" if provider.host else ""
            parts.append(f"{provider.remote}: {provider.label}{host}")
        return "; ".join(parts)

    @staticmethod
    def _is_conflict_resolution_plan(plan: LocalActionPlan) -> bool:
        if not plan.steps:
            return False
        return all(step.kind in _CONFLICT_RESOLUTION_STEPS for step in plan.steps)

    def _store_pending_plan(self, pending: PendingWritePlan) -> None:
        with self._pending_plans_lock:
            self._prune_expired_plans_locked()
            # Keep at most one approval-ready write plan per repository. A new
            # request replaces an older unapproved plan for that same repository.
            for existing_id, existing in list(self._pending_plans.items()):
                if existing.plan.repository_id == pending.plan.repository_id:
                    del self._pending_plans[existing_id]
            self._pending_plans[pending.plan.plan_id or ""] = pending

    def _take_pending_plan(self, repository_id: str, plan_id: str) -> PendingWritePlan:
        with self._pending_plans_lock:
            self._prune_expired_plans_locked()
            pending = self._pending_plans.pop(plan_id, None)

        if pending is None:
            raise ValidationFailure("This action plan is no longer available. Request a new plan.")
        if pending.plan.repository_id != repository_id:
            raise ValidationFailure("This action plan belongs to a different repository.")
        return pending

    def _prune_expired_plans_locked(self) -> None:
        now = monotonic()
        for plan_id, pending in list(self._pending_plans.items()):
            if pending.expires_at <= now:
                del self._pending_plans[plan_id]

    def _validate_push_step_against_current_repository(
        self,
        repository_id: str,
        step: ActionPlanStep,
    ) -> None:
        snapshot = self.snapshot(repository_id)
        if snapshot.write_blocked_reason:
            raise ValidationFailure(snapshot.write_blocked_reason)
        if snapshot.branch != step.branch:
            raise ValidationFailure(
                "The checked-out branch changed after approval. Request a new plan and review it again."
            )

        if step.set_upstream:
            # No upstream exists yet — only verify the remote is still reachable.
            if step.remote not in snapshot.remote_names:
                raise ValidationFailure(
                    f"Remote '{step.remote}' is no longer available. Request a new plan and review it again."
                )
        else:
            if snapshot.behind > 0:
                raise ValidationFailure(
                    "Push is blocked because the branch is now behind its upstream. Review the repository and request a new plan."
                )
            expected_upstream = f"{step.remote}/{step.branch}"
            if snapshot.upstream_remote != step.remote or snapshot.upstream_branch != expected_upstream:
                raise ValidationFailure(
                    "The current branch upstream changed after approval. Request a new plan and review it again."
                )

    def _validate_set_upstream_step_against_current_repository(
        self,
        repository_id: str,
        step: ActionPlanStep,
    ) -> None:
        snapshot = self.snapshot(repository_id)
        if snapshot.write_blocked_reason:
            raise ValidationFailure(snapshot.write_blocked_reason)
        if snapshot.branch != step.branch:
            raise ValidationFailure(
                "The checked-out branch changed after approval. Request a new plan and review it again."
            )
        if step.remote not in snapshot.remote_names:
            raise ValidationFailure(
                f"Remote '{step.remote}' is no longer available. Request a new plan and review it again."
            )

    def _with_plan_metadata(
        self,
        plan: LocalActionPlan,
        *,
        snapshot: RepositorySnapshot,
        privacy_receipt: PrivacyReceipt | None,
    ) -> LocalActionPlan:
        return plan.model_copy(
            update={
                "risk": self._score_plan(plan, snapshot),
                "privacy_receipt": privacy_receipt,
            }
        )

    def _score_plan(self, plan: LocalActionPlan, snapshot: RepositorySnapshot) -> PlanRisk:
        score = 5
        reasons: list[str] = []
        file_count = len({path for step in plan.steps for path in step.paths})

        if file_count >= 10:
            score += 15
            reasons.append(f"Touches {file_count} files.")
        elif file_count >= 4:
            score += 8
            reasons.append(f"Touches {file_count} files.")

        if snapshot.conflicts:
            score += 25
            reasons.append("Repository currently has conflicted paths.")
        if snapshot.behind > 0:
            score += 15
            reasons.append(f"Branch is behind upstream by {snapshot.behind} commit(s).")

        for step in plan.steps:
            if step.kind is PlanStepKind.COMMIT:
                score += 5
                reasons.append("Creates a local commit.")
            elif step.kind is PlanStepKind.PUSH:
                score += 20
                reasons.append("Publishes commits to a remote.")
                if step.set_upstream:
                    score += 5
                    reasons.append("Sets upstream tracking for the branch.")
            elif step.kind is PlanStepKind.PULL:
                score += 15
                reasons.append("Updates the working tree from a remote.")
            elif step.kind is PlanStepKind.SET_UPSTREAM:
                score += 12
                reasons.append("Sets upstream tracking for the current branch.")
            elif step.kind is PlanStepKind.DISCARD:
                score += 80
                reasons.append("Discards local file changes.")
            elif step.kind in {PlanStepKind.MERGE, PlanStepKind.MERGE_ABORT, PlanStepKind.MERGE_COMMIT}:
                score += 40
                reasons.append("Changes merge state.")
            elif step.kind is PlanStepKind.DELETE_BRANCH:
                score += 70
                reasons.append("Deletes a local branch.")
            elif step.kind is PlanStepKind.DELETE_TAG:
                score += 45
                reasons.append("Deletes a local tag.")
            elif step.kind is PlanStepKind.PUSH_TAG:
                score += 25
                reasons.append("Publishes a tag to a remote.")
            elif step.kind is PlanStepKind.CREATE_TAG:
                score += 15
                reasons.append("Creates a release tag.")
            elif step.kind in {PlanStepKind.ADD_REMOTE, PlanStepKind.RENAME_BRANCH}:
                score += 30
                reasons.append("Changes repository configuration.")
            elif step.kind in {PlanStepKind.STASH_DROP, PlanStepKind.STASH_POP}:
                score += 35
                reasons.append("Changes stash state.")
            elif step.kind is PlanStepKind.STASH:
                score += 15
                reasons.append("Moves work into the stash.")

        score = min(100, score)
        if score >= 70:
            level = "high"
            summary = "High risk - review the plan carefully before approval."
        elif score >= 35:
            level = "medium"
            summary = "Medium risk - review changed files and remote targets."
        else:
            level = "low"
            summary = "Low risk - local, reversible, or routine Git operation."

        if not reasons:
            reasons.append("No destructive or remote-publishing operation detected.")
        return PlanRisk(level=level, score=score, summary=summary, reasons=list(dict.fromkeys(reasons)))

    def _local_privacy_receipt(self, purpose: str) -> PrivacyReceipt:
        return PrivacyReceipt(
            external_provider=False,
            purpose=purpose,
            context_items=["Local repository metadata only"],
            exact_context="No external AI provider was contacted for this plan.",
        )

    def _llm_privacy_receipt(
        self,
        *,
        purpose: str,
        files: list[str],
        context_items: list[str],
        exact_context: str,
        truncated: bool = False,
    ) -> PrivacyReceipt:
        settings = self.settings_service.get_llm_settings() if self.settings_service is not None else None
        return PrivacyReceipt(
            external_provider=True,
            purpose=purpose,
            provider=settings.provider.value if settings and settings.provider else None,
            model=settings.model if settings else None,
            context_items=context_items,
            files=files,
            character_count=len(exact_context),
            truncated=truncated,
            exact_context=exact_context,
        )

    @staticmethod
    def _changed_paths(snapshot: RepositorySnapshot) -> list[str]:
        return list(
            dict.fromkeys(
                [
                    *[item.path for item in snapshot.staged_changes],
                    *[item.path for item in snapshot.modified_changes],
                    *[item.path for item in snapshot.untracked_paths],
                    *[item.path for item in snapshot.conflicts],
                ]
            )
        )

    @staticmethod
    def _normalise_commit_message_paths(
        paths: list[str],
        snapshot: RepositorySnapshot,
    ) -> list[str]:
        changed_paths = [
            *[item.path for item in snapshot.staged_changes],
            *[item.path for item in snapshot.modified_changes],
            *[item.path for item in snapshot.untracked_paths],
        ]
        changed_paths = list(dict.fromkeys(changed_paths))
        if not changed_paths:
            raise ValidationFailure("There are no changed files to summarize.")

        if not paths:
            return changed_paths[:40]

        allowed = set(changed_paths)
        normalised: list[str] = []
        for raw_path in paths:
            path = RepositoryService._normalise_requested_path(raw_path)
            if path not in allowed:
                raise ValidationFailure(
                    f"'{path}' is not a changed file in the selected repository."
                )
            normalised.append(path)
        return list(dict.fromkeys(normalised))

    @staticmethod
    def _changed_paths_from_snapshot(snapshot: RepositorySnapshot) -> list[str]:
        return list(dict.fromkeys([
            *[item.path for item in snapshot.staged_changes],
            *[item.path for item in snapshot.modified_changes],
            *[item.path for item in snapshot.untracked_paths],
        ]))

    @staticmethod
    def _normalise_publish_paths(paths: list[str], changed_paths: list[str]) -> list[str]:
        if not changed_paths:
            return []
        if not paths:
            return changed_paths

        allowed = set(changed_paths)
        normalised: list[str] = []
        for raw_path in paths:
            path = RepositoryService._normalise_requested_path(raw_path)
            if path not in allowed:
                raise ValidationFailure(
                    f"'{path}' is not a changed file in the selected repository."
                )
            normalised.append(path)
        return list(dict.fromkeys(normalised))

    @staticmethod
    def _build_ai_diff_context(
        canonical_path,
        paths: list[str],
        snapshot: RepositorySnapshot,
    ) -> AiDiffContext:
        client = GitClient(canonical_path)
        status_map = RepositoryService._ai_change_status_map(snapshot)
        stat_map = RepositoryService._ai_diff_stat_map(client, canonical_path, paths, snapshot)
        lines: list[str] = [f"Selected files: {len(paths)}"]
        lines.extend(
            [
                "",
                "Instruction: Generate one consolidated commit message for all selected files.",
                "",
                "Organized change map:",
            ]
        )
        lines.extend(RepositoryService._render_ai_change_map(paths, status_map, stat_map))
        context_items = ["Selected file paths", "Organized change map", "Diff stats"]
        team_context = RepositoryService._read_team_context(canonical_path)
        team_context_truncated = False
        if team_context:
            team_context_content, team_context_truncated = team_context
            lines.extend(
                [
                    "",
                    f"Repository team context ({_TEAM_CONTEXT_RELATIVE_PATH.as_posix()}):",
                    team_context_content,
                ]
            )
            context_items.append("Repository team context")
        if snapshot.recent_commits:
            lines.extend(
                [
                    "",
                    "Recent commit style examples:",
                    *[f"- {commit.subject}" for commit in snapshot.recent_commits[:5]],
                ]
            )
        if snapshot.recent_commits:
            context_items.append("Recent commit subjects")

        tracked_paths = {
            item.path
            for item in [*snapshot.staged_changes, *snapshot.modified_changes]
            if item.path in paths
        }
        untracked_paths = {
            item.path
            for item in snapshot.untracked_paths
            if item.path in paths
        }

        if tracked_paths:
            patch = client.diff_patch_for_paths(sorted(tracked_paths)).strip()
            if patch:
                lines.extend(["", "Patch:", patch])
                context_items.append("Tracked file patch")

        for path in sorted(untracked_paths):
            file_path = canonical_path / path
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lines.extend(
                [
                    "",
                    f"Untracked file: {path}",
                    content[:3000],
                ]
            )
            context_items.append("Untracked file snippets")

        context = "\n".join(lines)
        if len(context) <= _MAX_COMMIT_MESSAGE_CONTEXT_CHARS:
            return AiDiffContext(
                content=context,
                files=paths,
                context_items=list(dict.fromkeys(context_items)),
                truncated=team_context_truncated,
            )
        truncated_context = (
            context[:_MAX_COMMIT_MESSAGE_CONTEXT_CHARS]
            + "\n\n[Diff context truncated by AI Git Assistant.]"
        )
        return AiDiffContext(
            content=truncated_context,
            files=paths,
            context_items=list(dict.fromkeys(context_items)),
            truncated=True,
        )

    @staticmethod
    def _build_ai_pull_request_context(
        canonical_path,
        base_branch: str,
        head_branch: str,
        snapshot: RepositorySnapshot,
    ) -> AiDiffContext:
        client = GitClient(canonical_path)
        commits = client.log_range_oneline(f"{base_branch}..{head_branch}").strip()
        changed_files = client.compare_name_status(base_branch, head_branch).strip()
        diff_stat = client.compare_stat(base_branch, head_branch).strip()
        files = RepositoryService._paths_from_name_status(changed_files)
        lines: list[str] = [
            f"Base branch: {base_branch}",
            f"Head branch: {head_branch}",
            "",
            "Instruction: Generate one pull request title, body, and review checklist for this branch.",
            "",
            "Commits:",
            commits or "(No local commit range available.)",
            "",
            "Changed files:",
            changed_files or "(No local file list available.)",
            "",
            "Diff stat:",
            diff_stat or "(No local diff stat available.)",
        ]
        context_items = ["Branch names", "Commit range", "Changed files", "Diff stat"]
        team_context = RepositoryService._read_team_context(canonical_path)
        team_context_truncated = False
        if team_context:
            team_context_content, team_context_truncated = team_context
            lines.extend(
                [
                    "",
                    f"Repository team context ({_TEAM_CONTEXT_RELATIVE_PATH.as_posix()}):",
                    team_context_content,
                ]
            )
            context_items.append("Repository team context")
        if snapshot.recent_commits:
            lines.extend(
                [
                    "",
                    "Recent repository commit style examples:",
                    *[f"- {commit.subject}" for commit in snapshot.recent_commits[:5]],
                ]
            )
        if snapshot.recent_commits:
            context_items.append("Recent commit subjects")

        context = "\n".join(lines)
        context_truncated = len(context) > _MAX_COMMIT_MESSAGE_CONTEXT_CHARS
        if context_truncated:
            context = (
                context[:_MAX_COMMIT_MESSAGE_CONTEXT_CHARS]
                + "\n\n[Pull request context truncated by AI Git Assistant.]"
            )
        return AiDiffContext(
            content=context,
            files=files,
            context_items=context_items,
            truncated=context_truncated or team_context_truncated,
        )

    @staticmethod
    def _read_team_context(canonical_path: Path) -> tuple[str, bool] | None:
        context_path = canonical_path / _TEAM_CONTEXT_RELATIVE_PATH
        if not context_path.is_file():
            return None
        try:
            content = context_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return None
        if not content:
            return None
        if len(content) <= _TEAM_CONTEXT_MAX_CHARS:
            return content, False
        return (
            content[:_TEAM_CONTEXT_MAX_CHARS]
            + "\n\n[Repository team context truncated by AI Git Assistant.]",
            True,
        )

    @staticmethod
    def _paths_from_name_status(name_status: str) -> list[str]:
        paths: list[str] = []
        for line in name_status.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            if parts[0].startswith("R") and len(parts) >= 3:
                paths.append(parts[2])
            else:
                paths.append(parts[-1])
        return list(dict.fromkeys(paths))

    @staticmethod
    def _extract_pr_checklist(body: str) -> list[str]:
        checklist: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith(("- [ ]", "- [x]", "* [ ]", "* [x]")):
                checklist.append(stripped[5:].strip())
        if checklist:
            return checklist[:8]
        return [
            "Review changed files",
            "Run relevant tests",
            "Confirm CI passes",
        ]

    @staticmethod
    def _ai_change_status_map(snapshot: RepositorySnapshot) -> dict[str, str]:
        statuses: dict[str, str] = {}
        for item in snapshot.staged_changes:
            statuses[item.path] = RepositoryService._ai_change_label(item.index_status, fallback="staged")
        for item in snapshot.modified_changes:
            existing = statuses.get(item.path)
            label = RepositoryService._ai_change_label(item.worktree_status, fallback="modified")
            statuses[item.path] = f"{existing}, {label}" if existing else label
        for item in snapshot.untracked_paths:
            statuses[item.path] = "untracked"
        for item in snapshot.conflicts:
            statuses[item.path] = "conflict"
        return statuses

    @staticmethod
    def _render_ai_change_map(
        paths: list[str],
        status_map: dict[str, str],
        stat_map: dict[str, tuple[str, str]],
    ) -> list[str]:
        grouped: dict[str, list[str]] = {}
        for path in paths:
            group = RepositoryService._ai_change_group(path)
            grouped.setdefault(group, []).append(path)

        lines: list[str] = []
        for group in sorted(grouped):
            lines.append(f"Group: {group}")
            for path in sorted(grouped[group]):
                status = status_map.get(path, "changed")
                added, removed = stat_map.get(path, ("?", "?"))
                domain = RepositoryService._ai_change_domain(path)
                lines.append(f"- {path} [{status}; +{added}/-{removed}; {domain}]")
                lines.append(f"  Summary: {RepositoryService._ai_change_hint(path, status)}")
            lines.append("")
        if lines and lines[-1] == "":
            lines.pop()
        return lines

    @staticmethod
    def _ai_change_group(path: str) -> str:
        parts = PurePosixPath(path).parts
        if len(parts) >= 2:
            return "/".join(parts[:2])
        if parts:
            return parts[0]
        return "."

    @staticmethod
    def _ai_change_hint(path: str, status: str) -> str:
        if "deleted" in status:
            return "removed stale or replaced file content"
        if "untracked" in status:
            return "new file added to the change set"

        suffix = PurePosixPath(path).suffix.lower()
        if suffix == ".py":
            return "updated Python application logic"
        if suffix in {".tsx", ".ts", ".jsx", ".js"}:
            return "updated frontend or TypeScript behavior"
        if suffix in {".css", ".scss"}:
            return "updated interface styling"
        if suffix in {".md", ".mdx"}:
            return "updated documentation"
        if suffix in {".json", ".toml", ".yaml", ".yml"}:
            return "updated project configuration or structured data"
        if suffix in {".csv", ".tsv"}:
            return "updated generated or tabular data"
        return "updated file content"

    @staticmethod
    def _ai_change_domain(path: str) -> str:
        lower = path.lower()
        parts = PurePosixPath(lower).parts
        suffix = PurePosixPath(lower).suffix
        if (
            any(part in {"test", "tests", "__tests__", "spec"} for part in parts)
            or lower.endswith((".spec.ts", ".test.ts", ".spec.tsx", ".test.tsx", ".spec.js", ".test.js"))
        ):
            return "tests"
        if any(part in {"docs", "documentation"} for part in parts) or suffix in {".md", ".mdx"}:
            return "docs"
        if any(part in {"frontend", "src", "components", "pages", "ui"} for part in parts) and suffix in {".tsx", ".ts", ".jsx", ".js", ".css", ".scss"}:
            return "frontend"
        if any(part in {"backend", "sidecar", "api", "services", "app"} for part in parts) or suffix == ".py":
            return "backend"
        if suffix in {".json", ".toml", ".yaml", ".yml", ".lock"}:
            return "config"
        if suffix in {".csv", ".tsv", ".parquet", ".xlsx"} or "output" in parts or "generated" in parts:
            return "data"
        return "other"

    @staticmethod
    def _ai_diff_stat_map(
        client: GitClient,
        canonical_path,
        paths: list[str],
        snapshot: RepositorySnapshot,
    ) -> dict[str, tuple[str, str]]:
        stats: dict[str, tuple[str, str]] = {}
        raw = client.diff_numstat_for_paths(paths)
        for line in raw.splitlines():
            fields = line.split("\t")
            if len(fields) < 3:
                continue
            added, removed, path = fields[0], fields[1], fields[-1]
            stats[path] = (added, removed)

        for item in snapshot.untracked_paths:
            if item.path not in paths or item.path in stats:
                continue
            file_path = canonical_path / item.path
            if not file_path.is_file():
                continue
            try:
                line_count = len(file_path.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                line_count = 0
            stats[item.path] = (str(line_count), "0")
        return stats

    @staticmethod
    def _ai_change_label(code: str, *, fallback: str) -> str:
        labels = {
            "M": "modified",
            "A": "added",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "U": "unmerged",
        }
        return labels.get(code.strip(), fallback)

    def _validate_tag_push_step_against_current_repository(
        self,
        repository_id: str,
        step: ActionPlanStep,
    ) -> None:
        snapshot = self.snapshot(repository_id)
        if snapshot.write_blocked_reason:
            raise ValidationFailure(snapshot.write_blocked_reason)
        if step.remote not in snapshot.remote_names:
            raise ValidationFailure(
                f"Remote '{step.remote}' is no longer available. Request a new plan and review it again."
            )

    @staticmethod
    def _render_execution_result(
        plan: LocalActionPlan,
        snapshot: RepositorySnapshot,
    ) -> ActionExecutionResult:
        step_kinds = {step.kind for step in plan.steps}

        branch_step = next(
            (s for s in plan.steps if s.branch and s.kind in {
                PlanStepKind.SWITCH, PlanStepKind.CREATE_BRANCH, PlanStepKind.DELETE_BRANCH
            }),
            None,
        )

        if step_kinds == {PlanStepKind.STAGE}:
            title = "Files staged"
            summary = "Only the reviewed file paths were added to the staging area."
        elif PlanStepKind.PUSH in step_kinds and PlanStepKind.COMMIT in step_kinds:
            title = "Commit and push completed"
            summary = "The reviewed files were staged, committed locally, and pushed to the configured upstream."
        elif PlanStepKind.COMMIT in step_kinds:
            title = "Commit created"
            summary = "The reviewed commit was created locally."
        elif PlanStepKind.PUSH in step_kinds:
            title = "Push completed"
            summary = "The current branch was pushed to its configured upstream without force."
        elif step_kinds == {PlanStepKind.PULL}:
            title = "Pull completed"
            summary = "Local branch was fast-forwarded to match the upstream."
        elif step_kinds == {PlanStepKind.SET_UPSTREAM}:
            upstream_step = next((s for s in plan.steps if s.kind is PlanStepKind.SET_UPSTREAM), None)
            branch = upstream_step.branch if upstream_step else "current branch"
            remote = upstream_step.remote if upstream_step else "remote"
            title = "Upstream configured"
            summary = f"Local branch '{branch}' now tracks '{remote}/{branch}'."
        elif step_kinds == {PlanStepKind.UNSTAGE}:
            title = "Files unstaged"
            summary = "The selected files were moved back out of the staging area."
        elif step_kinds == {PlanStepKind.DISCARD}:
            title = "Changes discarded"
            summary = "The selected files were restored to their last committed state."
        elif step_kinds == {PlanStepKind.SWITCH}:
            br = branch_step.branch if branch_step else "branch"
            title = f"Switched to '{br}'"
            summary = f"Working tree is now on branch '{br}'."
        elif step_kinds == {PlanStepKind.CREATE_BRANCH}:
            br = branch_step.branch if branch_step else "branch"
            title = f"Branch '{br}' created"
            summary = f"New branch '{br}' was created from HEAD and checked out."
        elif step_kinds == {PlanStepKind.STASH}:
            title = "Changes stashed"
            summary = "Local changes were saved to the stash and the working tree was cleaned."
        elif step_kinds == {PlanStepKind.STASH_POP}:
            title = "Stash applied"
            summary = "The most recent stash entry was restored and removed from the stash list."
        elif step_kinds == {PlanStepKind.STASH_APPLY}:
            title = "Stash applied"
            summary = "The selected stash entry was restored and kept in the stash list."
        elif step_kinds == {PlanStepKind.STASH_DROP}:
            title = "Stash dropped"
            summary = "The selected stash entry was removed from the stash list."
        elif step_kinds == {PlanStepKind.MERGE}:
            merge_step = next((s for s in plan.steps if s.kind is PlanStepKind.MERGE), None)
            br = merge_step.branch if merge_step else "branch"
            title = f"Merged '{br}'"
            summary = f"Branch '{br}' was merged into the current branch."
        elif step_kinds == {PlanStepKind.MERGE_ABORT}:
            title = "Merge aborted"
            summary = "The in-progress merge was aborted and the pre-merge state was restored."
        elif step_kinds == {PlanStepKind.MERGE_COMMIT}:
            title = "Merge completed"
            summary = "The resolved merge was committed with Git's prepared merge message."
        elif step_kinds == {PlanStepKind.CREATE_TAG}:
            tag_step = next((s for s in plan.steps if s.kind is PlanStepKind.CREATE_TAG), None)
            tag = tag_step.tag_name if tag_step else "tag"
            title = f"Tag '{tag}' created"
            summary = f"Annotated local tag '{tag}' was created at the current HEAD."
        elif step_kinds == {PlanStepKind.DELETE_TAG}:
            tag_step = next((s for s in plan.steps if s.kind is PlanStepKind.DELETE_TAG), None)
            tag = tag_step.tag_name if tag_step else "tag"
            title = f"Tag '{tag}' deleted"
            summary = f"Local tag '{tag}' was deleted."
        elif step_kinds == {PlanStepKind.PUSH_TAG}:
            tag_step = next((s for s in plan.steps if s.kind is PlanStepKind.PUSH_TAG), None)
            tag = tag_step.tag_name if tag_step else "tag"
            remote = tag_step.remote if tag_step else "remote"
            title = f"Tag '{tag}' pushed"
            summary = f"Tag '{tag}' was pushed to '{remote}'."
        elif step_kinds == {PlanStepKind.DELETE_BRANCH}:
            br = branch_step.branch if branch_step else "branch"
            title = f"Branch '{br}' deleted"
            summary = f"Local branch '{br}' was deleted."
        elif step_kinds == {PlanStepKind.ADD_REMOTE}:
            remote_step = next((s for s in plan.steps if s.kind is PlanStepKind.ADD_REMOTE), None)
            rname = remote_step.remote if remote_step else "origin"
            title = f"Remote '{rname}' connected"
            summary = f"Remote '{rname}' was added. You can now push and pull with this repository."
        else:
            title = "Git actions completed"
            summary = "The reviewed local Git actions completed successfully."

        lines: list[str] = []
        for step in plan.steps:
            if step.kind is PlanStepKind.STAGE:
                lines.append(f"Staged {len(step.paths)} file{'s' if len(step.paths) != 1 else ''}:")
                lines.extend(f"- {path}" for path in step.paths)
            elif step.kind is PlanStepKind.COMMIT:
                commit = snapshot.recent_commits[0] if snapshot.recent_commits else None
                if commit:
                    lines.append(f"Commit: {commit.short_hash}  {commit.subject}")
                else:
                    lines.append("Commit created.")
            elif step.kind is PlanStepKind.PUSH:
                lines.append(f"Push: {step.branch} → {step.remote}/{step.branch}")
            elif step.kind is PlanStepKind.PULL:
                lines.append(f"Pull: {step.remote}/{step.branch} → {step.branch}")
            elif step.kind is PlanStepKind.SET_UPSTREAM:
                lines.append(f"Upstream: {step.branch} tracks {step.remote}/{step.branch}")
            elif step.kind is PlanStepKind.UNSTAGE:
                lines.append(f"Unstaged {len(step.paths)} file{'s' if len(step.paths) != 1 else ''}:")
                lines.extend(f"- {path}" for path in step.paths)
            elif step.kind is PlanStepKind.DISCARD:
                lines.append(f"Discarded changes in {len(step.paths)} file{'s' if len(step.paths) != 1 else ''}:")
                lines.extend(f"- {path}" for path in step.paths)
            elif step.kind is PlanStepKind.SWITCH:
                lines.append(f"Switched to branch '{step.branch}'")
            elif step.kind is PlanStepKind.CREATE_BRANCH:
                lines.append(f"Created and switched to branch '{step.branch}'")
            elif step.kind is PlanStepKind.STASH:
                label = f" ({step.commit_message})" if step.commit_message else ""
                lines.append(f"Stashed changes{label}")
            elif step.kind is PlanStepKind.STASH_POP:
                lines.append("Applied most recent stash entry")
            elif step.kind is PlanStepKind.STASH_APPLY:
                lines.append(f"Applied stash entry {step.stash_ref}")
            elif step.kind is PlanStepKind.STASH_DROP:
                lines.append(f"Dropped stash entry {step.stash_ref}")
            elif step.kind is PlanStepKind.MERGE:
                lines.append(f"Merged branch '{step.branch}'")
            elif step.kind is PlanStepKind.MERGE_ABORT:
                lines.append("Aborted in-progress merge")
            elif step.kind is PlanStepKind.MERGE_COMMIT:
                lines.append("Committed resolved merge")
            elif step.kind is PlanStepKind.CREATE_TAG:
                lines.append(f"Created annotated tag '{step.tag_name}'")
            elif step.kind is PlanStepKind.DELETE_TAG:
                lines.append(f"Deleted local tag '{step.tag_name}'")
            elif step.kind is PlanStepKind.PUSH_TAG:
                lines.append(f"Pushed tag '{step.tag_name}' to '{step.remote}'")
            elif step.kind is PlanStepKind.DELETE_BRANCH:
                lines.append(f"Deleted branch '{step.branch}'")
            elif step.kind is PlanStepKind.ADD_REMOTE:
                lines.append(f"Remote: {step.remote} → {step.remote_url}")
            elif step.kind is PlanStepKind.RENAME_BRANCH:
                lines.append(f"Branch renamed to '{step.branch}'")

        lines.extend(["", f"Ahead: {snapshot.ahead}", f"Behind: {snapshot.behind}"])
        return ActionExecutionResult(
            plan_id=plan.plan_id or "",
            title=title,
            summary=summary,
            content="\n".join(lines),
            snapshot=snapshot,
        )

    @staticmethod
    def _bounded_limit(value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationFailure("Log limit must be a number.") from exc
        return max(1, min(parsed, 50))

    @staticmethod
    def _bound_read_output(value: str) -> str:
        if len(value) <= _MAX_READ_OUTPUT_CHARS:
            return value
        return (
            value[:_MAX_READ_OUTPUT_CHARS]
            + "\n\n[Output truncated by AI Git Assistant. Narrow the request for the full output.]"
        )

    @staticmethod
    def _validate_stash_ref(value: str) -> None:
        if not _STASH_REF_PATTERN.fullmatch(value):
            raise ValidationFailure("Use an explicit stash reference such as stash@{0}.")

    @staticmethod
    def _validate_tag_name(value: str) -> None:
        candidate = value.strip()
        if (
            not _TAG_PATTERN.fullmatch(candidate)
            or ".." in candidate
            or "@{" in candidate
            or candidate.endswith(".")
            or candidate.endswith("/")
            or "//" in candidate
            or candidate.startswith("-")
        ):
            raise ValidationFailure("Use a safe tag name such as v0.3.0.")

    @staticmethod
    def _validate_pr_branch_name(value: str) -> None:
        candidate = value.strip()
        if (
            not _PR_BRANCH_PATTERN.fullmatch(candidate)
            or ".." in candidate
            or "@{" in candidate
            or candidate.endswith(".")
            or candidate.endswith("/")
            or "//" in candidate
            or candidate.startswith("-")
        ):
            raise ValidationFailure("Use a safe branch name such as main or feature/login.")

    @staticmethod
    def _normalise_requested_tag(value: str) -> str:
        candidate = value.strip().strip("`'\"").strip().rstrip(".!?")
        RepositoryService._validate_tag_name(candidate)
        return candidate

    @staticmethod
    def _normalise_requested_path(value: str) -> str:
        candidate = value.strip().strip("`'\"").strip().rstrip(".!?")
        candidate = candidate.removeprefix("./").replace("\\", "/")

        if (
            not candidate
            or candidate.startswith("/")
            or ":" in candidate
            or candidate == ".."
            or candidate.startswith("../")
            or "/../" in candidate
        ):
            raise ValidationFailure("Use a safe repository-relative file path without '..' or an absolute path.")

        return str(PurePosixPath(candidate))

    @staticmethod
    def _recent_commits(canonical_path) -> list[RecentCommit]:
        try:
            raw = GitClient(canonical_path).log(4)
        except GitCommandError:
            return []

        commits: list[RecentCommit] = []
        for record in raw.split("\x1e"):
            fields = record.strip().split("\x1f")
            if len(fields) != 5:
                continue
            commits.append(
                RecentCommit(
                    full_hash=fields[0],
                    short_hash=fields[1],
                    author=fields[2],
                    committed_at=fields[3],
                    subject=fields[4],
                )
            )
        return commits

    @staticmethod
    def _render_status(snapshot: RepositorySnapshot) -> str:
        def _label(code: str) -> str:
            return {
                "M": "modified",
                "A": "new file",
                "D": "deleted",
                "R": "renamed",
                "C": "copied",
                "U": "unmerged",
            }.get(code.strip(), "changed")

        lines: list[str] = [f"On branch {snapshot.branch or 'HEAD (detached)'}"]

        if snapshot.upstream_branch:
            a, b = snapshot.ahead, snapshot.behind
            if a == 0 and b == 0:
                lines.append(f"Your branch is up to date with '{snapshot.upstream_branch}'.")
            elif a > 0 and b == 0:
                lines.append(f"Your branch is ahead of '{snapshot.upstream_branch}' by {a} commit{'s' if a != 1 else ''}.")
            elif b > 0 and a == 0:
                lines.append(f"Your branch is behind '{snapshot.upstream_branch}' by {b} commit{'s' if b != 1 else ''}.")
            else:
                lines.append(f"Your branch and '{snapshot.upstream_branch}' have diverged (ahead {a}, behind {b}).")

        if snapshot.conflicts:
            lines += ["", "Unmerged paths:"]
            for cp in snapshot.conflicts:
                lines.append(f"\t{_label(cp.index_status)}:\t{cp.path}")

        if snapshot.staged_changes:
            lines += ["", "Changes staged for commit:"]
            for cp in snapshot.staged_changes:
                lines.append(f"\t{_label(cp.index_status)}:\t{cp.path}")

        if snapshot.modified_changes:
            lines += ["", "Changes not staged for commit:"]
            for cp in snapshot.modified_changes:
                lines.append(f"\t{_label(cp.worktree_status)}:\t{cp.path}")

        if snapshot.untracked_paths:
            lines += ["", "Untracked files:"]
            for cp in snapshot.untracked_paths:
                lines.append(f"\t{cp.path}")

        if not any([snapshot.staged_changes, snapshot.modified_changes,
                    snapshot.untracked_paths, snapshot.conflicts]):
            lines += ["", "Nothing to commit, working tree clean."]

        if snapshot.write_blocked_reason:
            lines += ["", f"Note: {snapshot.write_blocked_reason}"]

        return "\n".join(lines)

    @staticmethod
    def _render_conflicts(canonical_path, snapshot: RepositorySnapshot) -> str:
        if not snapshot.write_blocked_reason:
            return "No merge, cherry-pick, revert, rebase, or conflict workflow is in progress."

        lines: list[str] = [snapshot.write_blocked_reason]

        if not snapshot.conflicts:
            lines.extend(
                [
                    "",
                    "No conflicted paths are currently reported.",
                    "If this is a resolved merge, stage the resolved files and run:",
                    "  continue merge",
                    "",
                    "To abandon the merge instead, run:",
                    "  abort merge",
                ]
            )
            return "\n".join(lines)

        lines.extend(
            [
                "",
                "Conflicted files:",
                *[f"- {item.path}" for item in snapshot.conflicts],
                "",
                "Next steps:",
                "1. Use the recovery card to preview Keep local, Keep remote, or AI conflict resolution.",
                "2. Approve the preview to write and mark the files resolved.",
                "3. Run: continue merge",
                "",
                "Manual option:",
                "- Edit each file, remove <<<<<<<, =======, >>>>>>> markers, stage the resolved files, then run: continue merge",
                "",
                "To abandon this merge, run: abort merge",
            ]
        )

        for item in snapshot.conflicts[:5]:
            path = RepositoryService._normalise_requested_path(item.path)
            file_path = canonical_path / path
            if not file_path.is_file():
                continue
            try:
                raw = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            snippet = RepositoryService._conflict_marker_snippet(raw)
            if snippet:
                lines.extend(["", f"--- {path}", snippet])

        return RepositoryService._bound_read_output("\n".join(lines))

    @staticmethod
    def _conflict_marker_snippet(value: str) -> str:
        raw_lines = value.splitlines()
        marker_indexes = [
            index
            for index, line in enumerate(raw_lines)
            if line.startswith(("<<<<<<<", "=======", ">>>>>>>"))
        ]
        if not marker_indexes:
            return ""
        start = max(0, marker_indexes[0] - 4)
        end = min(len(raw_lines), marker_indexes[-1] + 5)
        return "\n".join(raw_lines[start:end])

    @staticmethod
    def _has_conflict_markers(value: str) -> bool:
        return any(
            line.startswith(("<<<<<<<", "=======", ">>>>>>>"))
            for line in value.splitlines()
        )

    @staticmethod
    def _resolve_conflict_markers(value: str, strategy: str) -> tuple[str, int]:
        if strategy not in {"ours", "theirs"}:
            raise ValidationFailure("Unsupported deterministic conflict resolution strategy.")

        lines = value.splitlines(keepends=True)
        output: list[str] = []
        ours: list[str] = []
        theirs: list[str] = []
        state = "normal"
        conflict_count = 0

        for line in lines:
            if state == "normal":
                if line.startswith("<<<<<<<"):
                    state = "ours"
                    ours = []
                    theirs = []
                    conflict_count += 1
                elif line.startswith(("=======", ">>>>>>>")):
                    raise ValidationFailure("Conflict markers are malformed. Resolve this file manually.")
                else:
                    output.append(line)
                continue

            if state == "ours":
                if line.startswith("======="):
                    state = "theirs"
                elif line.startswith(">>>>>>>"):
                    raise ValidationFailure("Conflict markers are malformed. Resolve this file manually.")
                else:
                    ours.append(line)
                continue

            if state == "theirs":
                if line.startswith(">>>>>>>"):
                    output.extend(ours if strategy == "ours" else theirs)
                    state = "normal"
                elif line.startswith("<<<<<<<") or line.startswith("======="):
                    raise ValidationFailure("Conflict markers are malformed. Resolve this file manually.")
                else:
                    theirs.append(line)

        if state != "normal":
            raise ValidationFailure("Conflict markers are incomplete. Resolve this file manually.")
        if conflict_count == 0:
            raise ValidationFailure("No conflict markers were found in the selected file.")
        return "".join(output), conflict_count

    @staticmethod
    def _preview_resolved_content(value: str) -> str:
        lines = value.splitlines()
        if len(lines) <= 80:
            return "\n".join(lines)
        head = "\n".join(lines[:60])
        tail = "\n".join(lines[-12:])
        omitted = len(lines) - 72
        return f"{head}\n\n... {omitted} line(s) omitted from preview ...\n\n{tail}"

    def _resolve_conflict_with_ai(self, path: str, content: str) -> tuple[str, int, str]:
        if self._llm_router is None:
            raise ValidationFailure("No AI provider is configured for conflict resolution.")
        conflict_count = sum(1 for line in content.splitlines() if line.startswith("<<<<<<<"))
        if conflict_count == 0:
            raise ValidationFailure(f"No conflict markers were found in '{path}'.")
        resolved = self._llm_router.resolve_conflict(path=path, conflicted_content=content)
        resolved = self._strip_ai_code_fence(resolved).strip()
        if not resolved:
            raise ValidationFailure("AI did not return resolved file content.")
        if self._has_conflict_markers(resolved):
            raise ValidationFailure("AI returned content that still contains conflict markers.")
        return resolved + ("\n" if content.endswith("\n") and not resolved.endswith("\n") else ""), conflict_count, "AI proposed a merged file."

    @staticmethod
    def _strip_ai_code_fence(value: str) -> str:
        stripped = value.strip()
        if not stripped.startswith("```"):
            return value
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1])
        return value

    @staticmethod
    def _render_log(raw: str) -> str:
        lines: list[str] = []
        for record in raw.split("\x1e"):
            fields = record.strip().split("\x1f")
            if len(fields) != 5:
                continue
            _, short_hash, author, committed_at, subject = fields
            lines.append(f"{short_hash}  {subject}\n  {author} · {committed_at}")
        return "\n".join(lines)

    @staticmethod
    def _render_branches(raw: str) -> str:
        branches: list[BranchInfo] = []

        for line in raw.splitlines():
            if not line:
                continue

            fields = line.split("\t", 2)
            if len(fields) < 2:
                continue

            head_marker, name = fields[0], fields[1]
            upstream = fields[2] if len(fields) > 2 and fields[2] else None

            branches.append(
                BranchInfo(
                    name=name,
                    is_current=head_marker == "*",
                    upstream=upstream,
                )
            )

        return "\n".join(
            f"{'*' if branch.is_current else ' '} {branch.name}"
            + (f"  → {branch.upstream}" if branch.upstream else "")
            for branch in branches
        )

    @staticmethod
    def _render_remotes(raw: str) -> str:
        entries: dict[str, dict[str, str]] = {}
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            name, url, kind = parts[0], parts[1], parts[2].strip("()")
            entries.setdefault(name, {})[kind] = url

        lines: list[str] = []
        for name, urls in sorted(entries.items()):
            fetch_url = urls.get("fetch")
            push_url = urls.get("push")
            if fetch_url and push_url and fetch_url != push_url:
                lines.append(f"{name}\n  fetch: {fetch_url}\n  push:  {push_url}")
            elif fetch_url or push_url:
                lines.append(f"{name}\n  url:   {fetch_url or push_url}")
        return "\n".join(lines)

    @staticmethod
    def _render_stashes(raw: str) -> str:
        lines: list[str] = []
        for record in raw.split("\x1e"):
            fields = record.strip().split("\x1f")
            if len(fields) != 3:
                continue
            stash_ref, relative_time, subject = fields
            lines.append(f"{stash_ref}  {relative_time}\n  {subject}")
        return "\n".join(lines)

    @staticmethod
    def _render_tags(raw: str) -> str:
        lines: list[str] = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            fields = line.split("\t", 2)
            tag_name = fields[0]
            created_at = fields[1] if len(fields) > 1 else ""
            subject = fields[2] if len(fields) > 2 else ""
            meta = f"  {created_at}" if created_at else ""
            lines.append(f"{tag_name}{meta}" + (f"\n  {subject}" if subject else ""))
        return "\n".join(lines)
