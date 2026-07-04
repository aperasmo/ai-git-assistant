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
from app.git.client import GitClient
from app.git.repository_inspector import RepositoryInspector
from app.intent.action_planner import LocalActionPlanner
from app.intent.local_matcher import LocalIntentMatcher
from app.schemas.repositories import (
    ActionExecutionResult,
    ActionPlanStep,
    BranchInfo,
    CancelActionPlanResponse,
    CommitMessageStyle,
    DraftGitHubReleaseRequest,
    DraftGitHubReleaseResponse,
    GenerateChangeSummaryResponse,
    FolderClassificationResponse,
    GenerateCommitMessageResponse,
    LocalActionPlan,
    PlanKind,
    PlanRisk,
    PlanStepKind,
    PrivacyReceipt,
    ReadAction,
    ReadActionRequest,
    ReadActionResult,
    RecentCommit,
    RepositoryResponse,
    RepositorySnapshot,
)
from app.services.repository_store import RepositoryStore
from app.services.github_release_service import GitHubReleaseClient, GitHubRepositoryRef, parse_github_remote_url

_logger = logging.getLogger("aiga.sidecar")

_PLAN_TTL_SECONDS = 5 * 60
_MAX_READ_OUTPUT_CHARS = 80_000
_MAX_COMMIT_MESSAGE_CONTEXT_CHARS = 14_000
_STASH_REF_PATTERN = re.compile(r"^stash@\{\d{1,3}\}$")
_TAG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_CONFLICT_RESOLUTION_STEPS = {
    PlanStepKind.STAGE,
    PlanStepKind.MERGE_ABORT,
    PlanStepKind.MERGE_COMMIT,
}


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
        if self._llm_router is None:
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
        new_lines = [p for p in paths if p not in existing_lines]
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

        asset_path: Path | None = None
        if request.asset_path:
            asset_path = Path(request.asset_path).expanduser()
            if not asset_path.is_file():
                raise ValidationFailure("The selected release asset does not exist or is not a file.")

        client = self._github_release_client_factory(token)
        result = client.create_draft_release(
            repository=repository_ref,
            tag_name=request.tag_name,
            title=request.title.strip(),
            body=request.body.strip(),
            target_commitish=snapshot.head_commit or snapshot.branch,
            prerelease=request.prerelease,
            asset_path=asset_path,
        )
        latest_snapshot = self.snapshot(repository_id)
        content_lines = [
            f"Repository: {repository_ref.slug}",
            f"Tag: {result.tag_name}",
            f"Release: {result.release_url}",
            "Draft: yes",
            f"Prerelease: {'yes' if request.prerelease else 'no'}",
        ]
        if result.asset_name:
            content_lines.extend(
                [
                    "",
                    f"Asset: {result.asset_name}",
                    f"Asset URL: {result.asset_url or '(not returned)'}",
                    f"SHA-256: {result.asset_sha256}",
                ]
            )

        return DraftGitHubReleaseResponse(
            tag_name=result.tag_name,
            repository=repository_ref.slug,
            release_url=result.release_url,
            asset_url=result.asset_url,
            asset_name=result.asset_name,
            asset_sha256=result.asset_sha256,
            title="GitHub Draft Release Created",
            summary="A draft GitHub release was created and the selected asset was uploaded.",
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
                    if step.set_upstream:
                        client.push_with_set_upstream(step.remote, step.branch)
                    else:
                        client.push_current_head(step.remote, step.branch)
                    completed_steps.append(step.title)
                    continue

                if step.kind is PlanStepKind.PULL:
                    client.pull_ff_only()
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
                    client.push_tag(step.remote, step.tag_name)
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
            client.fetch_prune()
            refreshed_at = datetime.now(UTC).isoformat()
            pre_snapshot = self.snapshot(repository_id)
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

        raise ValidationFailure("Unsupported read action.")

    @staticmethod
    def _github_repository_from_snapshot(snapshot: RepositorySnapshot) -> GitHubRepositoryRef:
        if not snapshot.remote_urls:
            raise ValidationFailure(
                "GitHub draft releases are not available because this repository has no remote. "
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
            "GitHub draft releases are not available for this repository. "
            f"Detected remote provider: {detected}. "
            "You can still use status, commits, branches, push, pull, fetch, tags, stash, merge, "
            "and AI summaries. GitLab, Bitbucket, and Azure DevOps release publishing are planned."
        )

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
        if snapshot.recent_commits:
            lines.extend(
                [
                    "",
                    "Recent commit style examples:",
                    *[f"- {commit.subject}" for commit in snapshot.recent_commits[:5]],
                ]
            )
        context_items = ["Selected file paths", "Organized change map", "Diff stats"]
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
                truncated=False,
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
                "1. Edit each file and keep the correct content.",
                "2. Remove the conflict markers: <<<<<<<, =======, >>>>>>>.",
                "3. Stage each resolved file in the app.",
                "4. Run: continue merge",
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
