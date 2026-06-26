from __future__ import annotations

import re
from pathlib import PurePosixPath

from app.errors import ValidationFailure
from app.intent.local_matcher import LocalIntentMatcher
from app.schemas.repositories import (
    ActionPlanStep,
    LocalActionPlan,
    PlanKind,
    PlanStepKind,
    ReadAction,
    RepositorySnapshot,
)

_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_PUSH_TAIL_PATTERN = re.compile(
    r"^,?\s*(?:then\s+)?push(?:\s+(?:current\s+branch|to\s+(?P<branch>[A-Za-z0-9._/-]+)))?\s*$",
    re.IGNORECASE,
)
_STAGE_PATTERN = re.compile(r"^\s*(?:stage|add)\s+(?P<paths>.+?)\s*[.!?]*$", re.IGNORECASE | re.DOTALL)
_PUSH_PATTERN = re.compile(
    r"^\s*push(?:\s+(?:current\s+branch|to\s+(?P<branch>[A-Za-z0-9._/-]+)))?\s*[.!?]*$",
    re.IGNORECASE,
)
_PULL_PATTERN = re.compile(
    r"^\s*(?:pull|sync\s+with\s+remote|git\s+pull)(?:\s+from\s+[A-Za-z0-9._/-]+)?\s*[.!?]*$",
    re.IGNORECASE,
)
_UNSTAGE_PATTERN = re.compile(
    r"^\s*unstage\s+(?P<paths>.+?)\s*[.!?]*$",
    re.IGNORECASE | re.DOTALL,
)
_UNSTAGE_REMOVE_PATTERN = re.compile(
    r"^\s*remove\s+(?P<paths>.+?)\s+from\s+(?:the\s+)?staging(?:\s+area)?\s*[.!?]*$",
    re.IGNORECASE | re.DOTALL,
)
_DISCARD_PATTERN = re.compile(
    r"^\s*discard(?:\s+changes?)?\s+(?:in\s+)?(?P<paths>.+?)\s*[.!?]*$",
    re.IGNORECASE | re.DOTALL,
)
_SWITCH_PATTERN = re.compile(
    r"^\s*(?:switch\s+to|checkout)\s+(?P<branch>[A-Za-z0-9._/-]+)\s*[.!?]*$",
    re.IGNORECASE,
)
_CREATE_BRANCH_PATTERN = re.compile(
    r"^\s*(?:create|new)\s+branch\s+(?P<branch>[A-Za-z0-9._/-]+)\s*[.!?]*$",
    re.IGNORECASE,
)
_STASH_POP_PATTERN = re.compile(
    r"^\s*(?:stash\s+pop|restore\s+stash|apply\s+stash)\s*[.!?]*$",
    re.IGNORECASE,
)
_STASH_PATTERN = re.compile(
    r"^\s*stash(?:\s+(?:my\s+)?changes?)?(?:\s+with\s+message\s+(?P<quote>[\"'])(?P<stash_msg>.+?)(?P=quote))?\s*[.!?]*$",
    re.IGNORECASE,
)
_DELETE_BRANCH_PATTERN = re.compile(
    r"^\s*(?:delete|remove)\s+branch\s+(?P<branch>[A-Za-z0-9._/-]+)\s*[.!?]*$",
    re.IGNORECASE,
)


class LocalActionPlanner:
    """Converts a deliberately small natural-language grammar into safe Git plans.

    This is not an LLM parser and it never executes Git itself. It recognises a
    bounded set of commands, resolves file references only against the selected
    repository's changed-file snapshot, and leaves execution to the service
    after explicit user approval.
    """

    def __init__(self, matcher: LocalIntentMatcher) -> None:
        self.matcher = matcher

    def plan(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
    ) -> LocalActionPlan:
        raw_message = message.strip()
        if not raw_message:
            raise ValidationFailure("Enter a Git request before submitting.")

        read_resolution = self.matcher.resolve(raw_message)
        if read_resolution.matched:
            return LocalActionPlan(
                matched=True,
                repository_id=repository_id,
                message=raw_message,
                plan_kind=PlanKind.READ,
                requires_confirmation=False,
                read_action=read_resolution.action,
                read_params=read_resolution.params,
                steps=[
                    ActionPlanStep(
                        kind=PlanStepKind.READ,
                        title=self._read_title(read_resolution.action),
                        detail=read_resolution.explanation,
                    )
                ],
                explanation=read_resolution.explanation,
            )

        commit_plan = self._plan_commit(repository_id, raw_message, snapshot)
        if commit_plan is not None:
            return commit_plan

        stage_match = _STAGE_PATTERN.match(raw_message)
        if stage_match:
            self._ensure_writes_allowed(snapshot)
            paths = self._resolve_paths(stage_match.group("paths"), snapshot, include_staged=True)
            return self._write_plan(
                repository_id=repository_id,
                message=raw_message,
                steps=[
                    ActionPlanStep(
                        kind=PlanStepKind.STAGE,
                        title=f"Stage {len(paths)} selected file{'s' if len(paths) != 1 else ''}",
                        detail="Add only the resolved paths to the Git staging area.",
                        paths=paths,
                        branch=snapshot.branch,
                        command_preview=self._command_preview("git", "add", "--", *paths),
                    )
                ],
            )

        push_match = _PUSH_PATTERN.match(raw_message)
        if push_match:
            self._ensure_writes_allowed(snapshot)
            push_step = self._build_push_step(snapshot, push_match.group("branch"))

            if snapshot.ahead == 0 and not push_step.set_upstream:
                branch = push_step.branch or "current branch"
                remote = push_step.remote or "configured upstream"

                return LocalActionPlan(
                    matched=True,
                    repository_id=repository_id,
                    message=raw_message,
                    plan_kind=PlanKind.INFO,
                    requires_confirmation=False,
                    steps=[
                        ActionPlanStep(
                            kind=PlanStepKind.PUSH,
                            title="Nothing to push",
                            detail=(
                                f"{branch} is already synchronized with "
                                f"{remote}/{branch}."
                            ),
                            remote=push_step.remote,
                            branch=push_step.branch,
                            ahead=push_step.ahead,
                            behind=push_step.behind,
                            force=push_step.force,
                            command_preview=push_step.command_preview,
                        )
                    ],
                    explanation=(
                        f"Nothing to push. {branch} is already synchronized "
                        f"with {remote}/{branch}."
                    ),
                )

            return self._write_plan(
                repository_id=repository_id,
                message=raw_message,
                steps=[push_step],
            )

        pull_match = _PULL_PATTERN.match(raw_message)
        if pull_match:
            return self._plan_pull(repository_id, raw_message, snapshot)

        unstage_match = _UNSTAGE_PATTERN.match(raw_message)
        if unstage_match:
            return self._plan_unstage(repository_id, raw_message, snapshot, unstage_match.group("paths"))

        unstage_remove_match = _UNSTAGE_REMOVE_PATTERN.match(raw_message)
        if unstage_remove_match:
            return self._plan_unstage(repository_id, raw_message, snapshot, unstage_remove_match.group("paths"))

        discard_match = _DISCARD_PATTERN.match(raw_message)
        if discard_match:
            return self._plan_discard(repository_id, raw_message, snapshot, discard_match.group("paths"))

        switch_match = _SWITCH_PATTERN.match(raw_message)
        if switch_match:
            return self._plan_switch(repository_id, raw_message, snapshot, switch_match.group("branch"))

        create_branch_match = _CREATE_BRANCH_PATTERN.match(raw_message)
        if create_branch_match:
            return self._plan_create_branch(repository_id, raw_message, snapshot, create_branch_match.group("branch"))

        stash_pop_match = _STASH_POP_PATTERN.match(raw_message)
        if stash_pop_match:
            return self._plan_stash_pop(repository_id, raw_message, snapshot)

        stash_match = _STASH_PATTERN.match(raw_message)
        if stash_match:
            return self._plan_stash(repository_id, raw_message, snapshot, stash_match.group("stash_msg"))

        delete_branch_match = _DELETE_BRANCH_PATTERN.match(raw_message)
        if delete_branch_match:
            return self._plan_delete_branch(repository_id, raw_message, snapshot, delete_branch_match.group("branch"))

        lowered = raw_message.lower().lstrip()
        if lowered.startswith("commit"):
            raise ValidationFailure(
                'Use a quoted commit message, for example: Commit src/login.py with message "Add login validation".'
            )
        if lowered.startswith(("stage", "add", "push")):
            raise ValidationFailure(
                "The requested Git action could not be planned. Use explicit repository-relative paths and a supported command pattern."
            )

        return LocalActionPlan(
            matched=False,
            repository_id=repository_id,
            message=raw_message,
            explanation=(
                "Supported local requests include status, diff, branches, recent commits, "
                "stage explicit paths, commit with a quoted message, and push the current branch."
            ),
        )

    def _plan_commit(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
    ) -> LocalActionPlan | None:
        if not re.match(r"^\s*commit\b", message, re.IGNORECASE):
            return None

        self._ensure_writes_allowed(snapshot)

        quoted_message = self._extract_quoted_commit_message(message)
        before_message = message[len("commit") : quoted_message.start].strip()
        target = re.sub(
            r"\bwith(?:\s+message)?\s*$",
            "",
            before_message,
            flags=re.IGNORECASE,
        )
        target = target.strip().rstrip(",").strip()

        if not target:
            raise ValidationFailure("Name the files to commit, or say 'commit staged changes'.")

        push_requested, requested_push_branch = self._parse_push_tail(message[quoted_message.end :])
        commit_message = quoted_message.value
        steps: list[ActionPlanStep] = []

        if self._is_staged_target(target):
            if not snapshot.staged_changes:
                raise ValidationFailure("There are no staged changes to commit.")

            commit_paths = list(
                dict.fromkeys(item.path for item in snapshot.staged_changes)
            )
        elif self._is_all_modified_target(target):
            all_changed = [*snapshot.modified_changes, *snapshot.untracked_paths]
            if not all_changed:
                raise ValidationFailure("There are no modified or untracked files to commit.")

            unrelated_staged = sorted({item.path for item in snapshot.staged_changes})
            if unrelated_staged:
                preview = ", ".join(unrelated_staged[:3])
                suffix = "…" if len(unrelated_staged) > 3 else ""
                raise ValidationFailure(
                    "There are already staged files outside your requested commit: "
                    f"{preview}{suffix}. Use 'commit staged changes' to include them, "
                    "or unstage them before committing all modified files."
                )

            selected_paths = list(dict.fromkeys(item.path for item in all_changed))
            steps.append(
                ActionPlanStep(
                    kind=PlanStepKind.STAGE,
                    title=f"Stage {len(selected_paths)} modified file{'s' if len(selected_paths) != 1 else ''}",
                    detail="Add all modified and untracked files to the Git staging area.",
                    paths=selected_paths,
                    branch=snapshot.branch,
                    command_preview=self._command_preview("git", "add", "--", *selected_paths),
                )
            )
            commit_paths = selected_paths
        else:
            selected_paths = self._resolve_paths(
                target,
                snapshot,
                include_staged=True,
            )
            selected_set = set(selected_paths)
            unrelated_staged = sorted(
                {
                    item.path
                    for item in snapshot.staged_changes
                    if item.path not in selected_set
                }
            )

            if unrelated_staged:
                preview = ", ".join(unrelated_staged[:3])
                suffix = "…" if len(unrelated_staged) > 3 else ""
                raise ValidationFailure(
                    "There are already staged files outside your requested commit: "
                    f"{preview}{suffix}. Use 'commit staged changes' to include them, "
                    "or unstage them before committing selected files."
                )

            steps.append(
                ActionPlanStep(
                    kind=PlanStepKind.STAGE,
                    title=(
                        f"Stage {len(selected_paths)} selected "
                        f"file{'s' if len(selected_paths) != 1 else ''}"
                    ),
                    detail="Add only the resolved paths to the Git staging area.",
                    paths=selected_paths,
                    branch=snapshot.branch,
                    command_preview=self._command_preview(
                        "git",
                        "add",
                        "--",
                        *selected_paths,
                    ),
                )
            )

            commit_paths = selected_paths

        steps.append(
            ActionPlanStep(
                kind=PlanStepKind.COMMIT,
                title="Create commit",
                detail="Create one local Git commit from the reviewed staging area.",
                paths=commit_paths,
                commit_message=commit_message,
                branch=snapshot.branch,
                command_preview=self._command_preview(
                    "git",
                    "commit",
                    "-m",
                    commit_message,
                ),
            )
        )

        if push_requested:
            steps.append(
                self._build_push_step(
                    snapshot,
                    requested_push_branch,
                    planned_commit_count=1,
                )
            )

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=steps,
        )

    @staticmethod
    def _extract_quoted_commit_message(message: str) -> "QuotedSegment":
        match = re.search(r"(?P<quote>[\"'])(?P<value>.+?)(?P=quote)", message, re.DOTALL)
        if match is None:
            raise ValidationFailure(
                'Commit messages must be enclosed in quotation marks, for example: "Add login validation".'
            )

        value = match.group("value").strip()
        if not value:
            raise ValidationFailure("Commit messages cannot be blank.")
        if "\x00" in value or "\n" in value or "\r" in value:
            raise ValidationFailure("Commit messages must be one line and cannot contain control characters.")
        if len(value) > 300:
            raise ValidationFailure("Commit messages must be 300 characters or fewer in v1.")

        return QuotedSegment(start=match.start(), end=match.end(), value=value)

    @staticmethod
    def _parse_push_tail(tail: str) -> tuple[bool, str | None]:
        cleaned = tail.strip().rstrip(".!?").strip()
        if not cleaned:
            return False, None

        match = _PUSH_TAIL_PATTERN.fullmatch(cleaned)
        if match is None:
            raise ValidationFailure(
                "After the quoted commit message, use only 'then push' or 'then push to <current-branch>'."
            )
        return True, match.group("branch")

    def _build_push_step(
        self,
        snapshot: RepositorySnapshot,
        requested_branch: str | None,
        *,
        planned_commit_count: int = 0,
    ) -> ActionPlanStep:
        branch = snapshot.branch
        remote = snapshot.upstream_remote
        upstream = snapshot.upstream_branch

        if not branch:
            raise ValidationFailure(
                "Push is unavailable because the repository is in detached HEAD state."
            )

        # --- Branch already has a configured upstream ---
        if remote and upstream and "/" in upstream:
            upstream_remote, upstream_branch = upstream.split("/", 1)

            if upstream_remote != remote:
                raise ValidationFailure(
                    "The configured upstream remote could not be validated safely."
                )
            if upstream_branch != branch:
                raise ValidationFailure(
                    "v1 pushes only the checked-out branch to the matching upstream branch. "
                    f"Current branch is '{branch}', but its upstream is '{upstream}'."
                )
            if snapshot.behind > 0:
                raise ValidationFailure(
                    "Push is blocked because the current branch is behind its upstream. "
                    "Fetch and integrate remote changes in your normal Git workflow first."
                )

            requested = self._normalise_requested_branch(requested_branch, remote)
            if requested is not None and requested != branch:
                raise ValidationFailure(
                    f"You are currently on '{branch}'. v1 will not silently push it to "
                    f"'{requested}'. Switch to the requested branch in your normal Git "
                    "workflow, then submit the request again."
                )

            return ActionPlanStep(
                kind=PlanStepKind.PUSH,
                title="Push current branch",
                detail="Push the checked-out branch to its configured upstream without force.",
                remote=remote,
                branch=branch,
                ahead=snapshot.ahead + planned_commit_count,
                behind=snapshot.behind,
                force=False,
                set_upstream=False,
                command_preview=self._command_preview("git", "push", remote, branch),
            )

        # --- No upstream yet: resolve a remote and push with --set-upstream ---
        if not snapshot.remote_names:
            raise ValidationFailure(
                "Push is unavailable because no Git remote is configured. "
                "Add a remote (e.g. 'git remote add origin <url>') in your normal Git workflow first."
            )

        push_remote, push_branch = self._resolve_set_upstream_target(
            requested_branch, branch, snapshot.remote_names
        )

        return ActionPlanStep(
            kind=PlanStepKind.PUSH,
            title="Push and set upstream",
            detail=(
                f"Push '{push_branch}' to '{push_remote}' and set it as the tracking "
                "upstream so future pushes work automatically."
            ),
            remote=push_remote,
            branch=push_branch,
            ahead=snapshot.ahead + planned_commit_count,
            behind=0,
            force=False,
            set_upstream=True,
            command_preview=self._command_preview(
                "git", "push", "--set-upstream", push_remote, push_branch
            ),
        )

    def _resolve_set_upstream_target(
        self,
        requested_branch: str | None,
        current_branch: str,
        remote_names: list[str],
    ) -> tuple[str, str]:
        """Return (remote, branch) for a --set-upstream push."""
        push_remote: str | None = None
        push_branch: str = current_branch

        if requested_branch:
            candidate = requested_branch.strip()
            # Allow "origin/dev_1" or "origin dev_1" style requests.
            for name in remote_names:
                if candidate.startswith(f"{name}/"):
                    push_remote = name
                    push_branch = candidate[len(name) + 1 :]
                    break
            else:
                # Treat it as a bare branch name; remote resolved below.
                push_branch = self._normalise_requested_branch(requested_branch, remote_names[0]) or current_branch

        if push_remote is None:
            if "origin" in remote_names:
                push_remote = "origin"
            elif len(remote_names) == 1:
                push_remote = remote_names[0]
            else:
                names = ", ".join(remote_names)
                raise ValidationFailure(
                    f"Multiple remotes are configured ({names}). "
                    "Specify the target in your request, e.g. 'push to origin/dev_1'."
                )

        if push_branch != current_branch:
            raise ValidationFailure(
                f"You are currently on '{current_branch}'. v1 will not silently push it to "
                f"'{push_branch}'. Switch to the requested branch in your normal Git "
                "workflow, then submit the request again."
            )

        return push_remote, push_branch

    def _plan_pull(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)
        branch = snapshot.branch
        remote = snapshot.upstream_remote
        upstream = snapshot.upstream_branch

        if not branch:
            raise ValidationFailure("Pull is unavailable because the repository is in detached HEAD state.")

        if not remote or not upstream:
            return LocalActionPlan(
                matched=True,
                repository_id=repository_id,
                message=message,
                plan_kind=PlanKind.INFO,
                requires_confirmation=False,
                steps=[
                    ActionPlanStep(
                        kind=PlanStepKind.PULL,
                        title="No upstream configured",
                        detail=(
                            f"'{branch}' has no tracking upstream. "
                            "Push the branch first or run fetch to sync remote tracking references."
                        ),
                        branch=branch,
                    )
                ],
                explanation=f"'{branch}' has no configured upstream to pull from.",
            )

        if snapshot.ahead > 0 and snapshot.behind > 0:
            raise ValidationFailure(
                f"Your branch has diverged from '{upstream}' — "
                f"{snapshot.ahead} commit(s) ahead and {snapshot.behind} behind. "
                "Fast-forward pull is not possible. Integrate remote changes manually."
            )

        if snapshot.behind == 0:
            return LocalActionPlan(
                matched=True,
                repository_id=repository_id,
                message=message,
                plan_kind=PlanKind.INFO,
                requires_confirmation=False,
                steps=[
                    ActionPlanStep(
                        kind=PlanStepKind.PULL,
                        title="Already up to date",
                        detail=f"'{branch}' is already synchronised with '{upstream}'.",
                        remote=remote,
                        branch=branch,
                        behind=0,
                    )
                ],
                explanation=f"'{branch}' is already up to date with '{upstream}'.",
            )

        commits = snapshot.behind
        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.PULL,
                    title=f"Pull {commits} commit{'s' if commits != 1 else ''} from {remote}",
                    detail=(
                        f"Fast-forward '{branch}' to match '{upstream}'. "
                        f"Your branch is {commits} commit{'s' if commits != 1 else ''} behind."
                    ),
                    remote=remote,
                    branch=branch,
                    behind=commits,
                    command_preview=self._command_preview("git", "pull", "--ff-only"),
                )
            ],
        )

    def _plan_unstage(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        paths_expr: str,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)
        paths = self._resolve_paths(paths_expr, snapshot, staged_only=True)
        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.UNSTAGE,
                    title=f"Unstage {len(paths)} file{'s' if len(paths) != 1 else ''}",
                    detail="Move the selected files back out of the staging area. The changes are kept in the working tree.",
                    paths=paths,
                    command_preview=self._command_preview("git", "restore", "--staged", "--", *paths),
                )
            ],
        )

    def _plan_discard(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        paths_expr: str,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)
        paths = self._resolve_paths(paths_expr, snapshot, modified_only=True)
        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.DISCARD,
                    title=f"Discard changes in {len(paths)} file{'s' if len(paths) != 1 else ''}",
                    detail=(
                        "DESTRUCTIVE — Revert the selected files to their last committed state. "
                        "All local modifications to these files will be permanently lost."
                    ),
                    paths=paths,
                    command_preview=self._command_preview("git", "restore", "--", *paths),
                )
            ],
        )

    def _plan_switch(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        target_branch: str,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)

        if not _BRANCH_PATTERN.fullmatch(target_branch) or ".." in target_branch or "@{" in target_branch:
            raise ValidationFailure(f"'{target_branch}' is not a valid branch name.")

        if target_branch == snapshot.branch:
            return LocalActionPlan(
                matched=True,
                repository_id=repository_id,
                message=message,
                plan_kind=PlanKind.INFO,
                requires_confirmation=False,
                steps=[
                    ActionPlanStep(
                        kind=PlanStepKind.SWITCH,
                        title=f"Already on '{target_branch}'",
                        detail=f"The working tree is already on branch '{target_branch}'.",
                        branch=target_branch,
                    )
                ],
                explanation=f"Already on '{target_branch}'.",
            )

        if snapshot.staged_changes or snapshot.modified_changes:
            raise ValidationFailure(
                f"You have uncommitted changes. Stash or commit them before switching to '{target_branch}'."
            )

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.SWITCH,
                    title=f"Switch to '{target_branch}'",
                    detail=f"Check out branch '{target_branch}'. The working tree must be clean.",
                    branch=target_branch,
                    command_preview=self._command_preview("git", "switch", target_branch),
                )
            ],
        )

    def _plan_create_branch(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        branch_name: str,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)

        if not _BRANCH_PATTERN.fullmatch(branch_name) or ".." in branch_name or "@{" in branch_name or branch_name.endswith("."):
            raise ValidationFailure(f"'{branch_name}' is not a valid branch name.")

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.CREATE_BRANCH,
                    title=f"Create branch '{branch_name}'",
                    detail=f"Create new local branch '{branch_name}' from the current HEAD and switch to it.",
                    branch=branch_name,
                    command_preview=self._command_preview("git", "switch", "-c", branch_name),
                )
            ],
        )

    def _plan_stash(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        stash_message: str | None,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)

        if not snapshot.staged_changes and not snapshot.modified_changes:
            raise ValidationFailure("There are no local changes to stash.")

        count = len(snapshot.staged_changes) + len(snapshot.modified_changes)
        cmd_args = ["git", "stash", "push"]
        if stash_message:
            cmd_args.extend(["-m", stash_message])

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.STASH,
                    title="Stash local changes",
                    detail=(
                        f"Save {count} change{'s' if count != 1 else ''} to the stash "
                        "and restore the working tree to HEAD."
                    ),
                    commit_message=stash_message,
                    command_preview=self._command_preview(*cmd_args),
                )
            ],
        )

    def _plan_stash_pop(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.STASH_POP,
                    title="Apply stash",
                    detail=(
                        "Restore the most recent stash entry and remove it from the stash list. "
                        "Execution is blocked if applying the stash would cause conflicts."
                    ),
                    command_preview=self._command_preview("git", "stash", "pop"),
                )
            ],
        )

    def _plan_delete_branch(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        branch_name: str,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)

        if not _BRANCH_PATTERN.fullmatch(branch_name) or ".." in branch_name or "@{" in branch_name:
            raise ValidationFailure(f"'{branch_name}' is not a valid branch name.")

        if branch_name == snapshot.branch:
            raise ValidationFailure(
                f"Cannot delete '{branch_name}' because it is the currently checked-out branch. "
                "Switch to a different branch first."
            )

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.DELETE_BRANCH,
                    title=f"Delete branch '{branch_name}'",
                    detail=(
                        f"Delete local branch '{branch_name}'. "
                        "Safe delete only — fails if the branch has commits not merged into another branch."
                    ),
                    branch=branch_name,
                    command_preview=self._command_preview("git", "branch", "-d", branch_name),
                )
            ],
        )

    @staticmethod
    def _command_preview(*arguments: str) -> str:
        return " ".join(
            LocalActionPlanner._quote_command_argument(argument)
            for argument in arguments
        )

    @staticmethod
    def _quote_command_argument(value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9_./:@%+=,-]+", value):
            return value

        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("$", "\\$")
            .replace("`", "\\`")
            .replace("!", "\\!")
        )
        return f'"{escaped}"'
    @staticmethod
    def _normalise_requested_branch(requested: str | None, remote: str) -> str | None:
        if requested is None:
            return None

        candidate = requested.strip()
        remote_prefix = f"{remote}/"
        if candidate.startswith(remote_prefix):
            candidate = candidate.removeprefix(remote_prefix)

        if (
            not candidate
            or not _BRANCH_PATTERN.fullmatch(candidate)
            or ".." in candidate
            or "@{" in candidate
            or candidate.endswith(".")
        ):
            raise ValidationFailure("The requested branch name is not valid for this v1 planner.")
        return candidate

    def _resolve_paths(
        self,
        expression: str,
        snapshot: RepositorySnapshot,
        *,
        include_staged: bool = True,
        staged_only: bool = False,
        modified_only: bool = False,
    ) -> list[str]:
        raw_parts = re.split(r"\s*(?:,|\band\b)\s*", expression, flags=re.IGNORECASE)
        parts = [self._normalise_requested_path(part) for part in raw_parts if part.strip()]

        if not parts:
            raise ValidationFailure("Name at least one repository-relative file path.")

        forbidden = {"all", "all files", "everything", ".", "*", "all changes", "all modifications"}
        if any(part.casefold() in forbidden for part in parts):
            raise ValidationFailure("v1 requires explicit file paths and does not support 'all files' or 'git add .'.")

        if staged_only:
            candidates = list(snapshot.staged_changes)
            if not candidates:
                raise ValidationFailure("There are no staged files to unstage.")
        elif modified_only:
            candidates = list(snapshot.modified_changes)
            if not candidates:
                raise ValidationFailure("There are no modified files to discard changes from.")
        else:
            candidates = [*snapshot.modified_changes, *snapshot.untracked_paths]
            if include_staged:
                candidates.extend(snapshot.staged_changes)

        actual_paths = list(dict.fromkeys(item.path for item in candidates))
        if not actual_paths:
            raise ValidationFailure("There are no changed files available to resolve in this repository.")

        normalised_actual = {self._normalise_snapshot_path(path): path for path in actual_paths}
        resolved: list[str] = []

        for requested in parts:
            if requested in normalised_actual:
                resolved.append(normalised_actual[requested])
                continue

            matches = [
                actual
                for normalised, actual in normalised_actual.items()
                if normalised.endswith(f"/{requested}") or PurePosixPath(normalised).name == requested
            ]
            matches = list(dict.fromkeys(matches))

            if not matches:
                raise ValidationFailure(
                    f"'{requested}' is not a changed file in the selected repository. "
                    "Use a repository-relative path from the status panel."
                )
            if len(matches) > 1:
                preview = ", ".join(matches[:4])
                raise ValidationFailure(
                    f"'{requested}' is ambiguous. Use a longer repository-relative path. Matches: {preview}"
                )
            resolved.append(matches[0])

        return list(dict.fromkeys(resolved))

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
    def _normalise_snapshot_path(value: str) -> str:
        return str(PurePosixPath(value.replace("\\", "/")))

    @staticmethod
    def _is_staged_target(target: str) -> bool:
        return target.casefold().strip() in {
            "staged changes",
            "staged files",
            "all staged changes",
            "all staged files",
        }

    @staticmethod
    def _is_all_modified_target(target: str) -> bool:
        return target.casefold().strip() in {
            "all modified files",
            "all modified",
            "modified files",
            "all changes",
            "all my changes",
            "my changes",
            "changes",
            "changed files",
            "all unstaged files",
            "unstaged files",
            "everything",
        }

    @staticmethod
    def _ensure_writes_allowed(snapshot: RepositorySnapshot) -> None:
        if snapshot.write_blocked_reason:
            raise ValidationFailure(snapshot.write_blocked_reason)

    @staticmethod
    def _write_plan(
        *,
        repository_id: str,
        message: str,
        steps: list[ActionPlanStep],
    ) -> LocalActionPlan:
        return LocalActionPlan(
            matched=True,
            repository_id=repository_id,
            message=message,
            plan_kind=PlanKind.WRITE,
            requires_confirmation=True,
            steps=steps,
            explanation="Review the exact local Git actions below. Nothing has changed yet.",
        )

    @staticmethod
    def _read_title(action: ReadAction | None) -> str:
        titles = {
            ReadAction.STATUS: "Read Git status",
            ReadAction.LOG: "Read recent commits",
            ReadAction.DIFF: "Read diff summary",
            ReadAction.BRANCHES: "Read local branches",
            ReadAction.FETCH: "Refresh remote status",
        }
        return titles.get(action, "Read local repository state")


class QuotedSegment:
    def __init__(self, *, start: int, end: int, value: str) -> None:
        self.start = start
        self.end = end
        self.value = value
