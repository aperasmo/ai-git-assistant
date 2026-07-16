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
_TAG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
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
_SET_UPSTREAM_PATTERN = re.compile(
    r"^\s*(?:set\s+upstream|set\s+tracking|track\s+remote)"
    r"(?:\s+(?:to|as))?\s+"
    r"(?:(?P<remote>[A-Za-z0-9._-]+)\/)?(?P<branch>[A-Za-z0-9._/-]+)\s*[.!?]*$",
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
_MERGE_ABORT_PATTERN = re.compile(
    r"^\s*(?:abort\s+merge|merge\s+abort|cancel\s+merge)\s*[.!?]*$",
    re.IGNORECASE,
)
_MERGE_COMMIT_PATTERN = re.compile(
    r"^\s*(?:continue\s+merge|finish\s+merge|commit\s+merge)\s*[.!?]*$",
    re.IGNORECASE,
)
_MERGE_PATTERN = re.compile(
    r"^\s*merge\s+(?P<branch>[A-Za-z0-9._/-]+)(?:\s+into\s+[A-Za-z0-9._/-]+)?\s*[.!?]*$",
    re.IGNORECASE,
)
_STASH_REF_PATTERN = re.compile(r"^stash@\{(?P<index>\d{1,3})\}$")
_STASH_APPLY_PATTERN = re.compile(
    r"^\s*(?:apply|restore)\s+stash\s+(?P<stash_ref>stash@\{\d{1,3}\})\s*[.!?]*$",
    re.IGNORECASE,
)
_STASH_DROP_PATTERN = re.compile(
    r"^\s*(?:drop|delete|remove)\s+stash\s+(?P<stash_ref>stash@\{\d{1,3}\})\s*[.!?]*$",
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
_CREATE_TAG_PATTERN = re.compile(
    r"^\s*(?:create\s+)?(?:annotated\s+)?tag\s+(?P<tag>[A-Za-z0-9][A-Za-z0-9._/-]{0,254})\s+"
    r"(?:with\s+)?(?:message\s+(?:is\s+)?)?(?P<quote>[\"'])(?P<tag_msg>.+?)(?P=quote)\s*[.!?]*$",
    re.IGNORECASE | re.DOTALL,
)
_DELETE_TAG_PATTERN = re.compile(
    r"^\s*(?:delete|remove)\s+tag\s+(?P<tag>[A-Za-z0-9][A-Za-z0-9._/-]{0,254})\s*[.!?]*$",
    re.IGNORECASE,
)
_PUSH_TAG_PATTERN = re.compile(
    r"^\s*push\s+tag\s+(?P<tag>[A-Za-z0-9][A-Za-z0-9._/-]{0,254})(?:\s+to\s+(?P<remote>[A-Za-z0-9._-]+))?\s*[.!?]*$",
    re.IGNORECASE,
)
_STAGE_ALL_THEN_COMMIT_PATTERN = re.compile(
    r"^\s*(?:stage|add)\s+"
    r"(?:all(?:\s+(?:files?|changes?|modified(?:\s+files?)?))?|everything|(?:my\s+)?changes?)\s*"
    r",?\s*(?:then\s+|and\s+)?"
    r"commit(?P<push_inline>\s+and\s+push)?\s*"
    r"(?:with\s+)?(?:message\s+(?:is\s+)?)?(?P<quote>[\"'])(?P<commit_msg>.+?)(?P=quote)"
    r"(?P<push_tail>.*)$",
    re.IGNORECASE | re.DOTALL,
)
# Detects "and push" / "then push" appearing before the quoted message
_PUSH_PREFIX_PATTERN = re.compile(
    r",?\s*\b(?:and|then)\s+push(?:\s+(?:current\s+branch|to\s+[A-Za-z0-9._/-]+))?\s*",
    re.IGNORECASE,
)
# Matches "push and commit [all/changes/...] with message '...'"
_PUSH_AND_COMMIT_PATTERN = re.compile(
    r"^\s*push\s+and\s+commit\s+"
    r"(?:all(?:\s+the)?(?:\s+(?:files?|changes?|modified(?:\s+files?)?))?|everything|(?:my\s+|the\s+)?(?:all\s+)?changes?)\s*"
    r"(?:with\s+)?(?:message\s+(?:is\s+)?)?(?P<quote>[\"'])(?P<commit_msg>.+?)(?P=quote)"
    r"(?P<push_tail>.*)$",
    re.IGNORECASE | re.DOTALL,
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

        push_and_commit_match = _PUSH_AND_COMMIT_PATTERN.match(raw_message)
        if push_and_commit_match:
            commit_msg = push_and_commit_match.group("commit_msg")
            rewritten = f'commit all modified files with message "{commit_msg}", then push'
            return self._plan_commit(repository_id, rewritten, snapshot)  # type: ignore[return-value]

        stage_all_commit_match = _STAGE_ALL_THEN_COMMIT_PATTERN.match(raw_message)
        if stage_all_commit_match:
            commit_msg = stage_all_commit_match.group("commit_msg")
            push_requested = bool(
                stage_all_commit_match.group("push_inline")
                or _PUSH_TAIL_PATTERN.match(stage_all_commit_match.group("push_tail") or "")
            )
            suffix = ", then push" if push_requested else ""
            rewritten = f'commit all modified files with message "{commit_msg}"{suffix}'
            return self._plan_commit(repository_id, rewritten, snapshot)  # type: ignore[return-value]

        stage_match = _STAGE_PATTERN.match(raw_message)
        if stage_match:
            if snapshot.write_blocked_reason and not snapshot.conflicts:
                self._ensure_writes_allowed(snapshot)
            paths = self._resolve_paths(
                stage_match.group("paths"),
                snapshot,
                include_staged=True,
                include_conflicts=bool(snapshot.conflicts),
            )
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

        set_upstream_match = _SET_UPSTREAM_PATTERN.match(raw_message)
        if set_upstream_match:
            return self._plan_set_upstream(
                repository_id,
                raw_message,
                snapshot,
                set_upstream_match.group("remote"),
                set_upstream_match.group("branch"),
            )

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

        merge_abort_match = _MERGE_ABORT_PATTERN.match(raw_message)
        if merge_abort_match:
            return self._plan_merge_abort(repository_id, raw_message, snapshot)

        merge_commit_match = _MERGE_COMMIT_PATTERN.match(raw_message)
        if merge_commit_match:
            return self._plan_merge_commit(repository_id, raw_message, snapshot)

        merge_match = _MERGE_PATTERN.match(raw_message)
        if merge_match:
            return self._plan_merge(repository_id, raw_message, snapshot, merge_match.group("branch"))

        stash_apply_match = _STASH_APPLY_PATTERN.match(raw_message)
        if stash_apply_match:
            return self._plan_stash_apply(repository_id, raw_message, snapshot, stash_apply_match.group("stash_ref"))

        stash_drop_match = _STASH_DROP_PATTERN.match(raw_message)
        if stash_drop_match:
            return self._plan_stash_drop(repository_id, raw_message, snapshot, stash_drop_match.group("stash_ref"))

        stash_pop_match = _STASH_POP_PATTERN.match(raw_message)
        if stash_pop_match:
            return self._plan_stash_pop(repository_id, raw_message, snapshot)

        stash_match = _STASH_PATTERN.match(raw_message)
        if stash_match:
            return self._plan_stash(repository_id, raw_message, snapshot, stash_match.group("stash_msg"))

        delete_branch_match = _DELETE_BRANCH_PATTERN.match(raw_message)
        if delete_branch_match:
            return self._plan_delete_branch(repository_id, raw_message, snapshot, delete_branch_match.group("branch"))

        create_tag_match = _CREATE_TAG_PATTERN.match(raw_message)
        if create_tag_match:
            return self._plan_create_tag(
                repository_id,
                raw_message,
                snapshot,
                create_tag_match.group("tag"),
                create_tag_match.group("tag_msg"),
            )

        delete_tag_match = _DELETE_TAG_PATTERN.match(raw_message)
        if delete_tag_match:
            return self._plan_delete_tag(repository_id, raw_message, snapshot, delete_tag_match.group("tag"))

        push_tag_match = _PUSH_TAG_PATTERN.match(raw_message)
        if push_tag_match:
            return self._plan_push_tag(
                repository_id,
                raw_message,
                snapshot,
                push_tag_match.group("tag"),
                push_tag_match.group("remote"),
            )

        return LocalActionPlan(
            matched=False,
            repository_id=repository_id,
            message=raw_message,
            explanation=(
                "The local planner did not recognise this request. "
                "If you have an AI provider configured and enabled for this repository, "
                "it will handle the request automatically."
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

        # Strip "and push" / "then push" that appears before the quoted message
        push_in_prefix = bool(_PUSH_PREFIX_PATTERN.search(before_message))
        before_message = _PUSH_PREFIX_PATTERN.sub(" ", before_message).strip()

        # Strip message connectors: "with message", "message is", "with", etc.
        target = re.sub(
            r"\b(?:with\s+)?message\s+is\s*$|\bwith(?:\s+message)?\s*$",
            "",
            before_message,
            flags=re.IGNORECASE,
        )
        target = target.strip().rstrip(",").strip()

        if not target:
            # "commit and push with message '...'" with no explicit target → all modified
            target = "changes"

        push_requested_tail, requested_push_branch = self._parse_push_tail(message[quoted_message.end :])
        push_requested = push_in_prefix or push_requested_tail
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
            likely_remote = "origin" if "origin" in snapshot.remote_names else (
                snapshot.remote_names[0] if len(snapshot.remote_names) == 1 else None
            )
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
                            + (
                                f"Set the upstream to {likely_remote}/{branch}, then pull latest."
                                if likely_remote else
                                "Connect a remote first, then set upstream before pulling."
                            )
                        ),
                        remote=likely_remote,
                        branch=branch,
                        command_preview=(
                            self._command_preview(
                                "git", "branch", "--set-upstream-to", f"{likely_remote}/{branch}", branch
                            )
                            if likely_remote else None
                        ),
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

    def _plan_set_upstream(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        requested_remote: str | None,
        requested_branch: str,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)
        current_branch = snapshot.branch
        if not current_branch:
            raise ValidationFailure("Upstream setup is unavailable because the repository is in detached HEAD state.")

        remote_names = snapshot.remote_names
        if not remote_names:
            raise ValidationFailure("Upstream setup is unavailable because no Git remote is configured.")

        remote = requested_remote
        branch = self._normalise_requested_branch(requested_branch, requested_remote or "origin")
        if branch is None:
            branch = current_branch

        if remote is None:
            if "origin" in remote_names:
                remote = "origin"
            elif len(remote_names) == 1:
                remote = remote_names[0]
            else:
                names = ", ".join(remote_names)
                raise ValidationFailure(
                    f"Multiple remotes are configured ({names}). Specify the target, e.g. 'set upstream to origin/{current_branch}'."
                )

        if remote not in remote_names:
            raise ValidationFailure(f"Remote '{remote}' is not configured for this repository.")

        if branch != current_branch:
            raise ValidationFailure(
                f"You are currently on '{current_branch}'. Set upstream for the checked-out branch, "
                f"for example 'set upstream to {remote}/{current_branch}'."
            )

        if snapshot.upstream_remote == remote and snapshot.upstream_branch == f"{remote}/{branch}":
            return LocalActionPlan(
                matched=True,
                repository_id=repository_id,
                message=message,
                plan_kind=PlanKind.INFO,
                requires_confirmation=False,
                steps=[
                    ActionPlanStep(
                        kind=PlanStepKind.SET_UPSTREAM,
                        title="Upstream already configured",
                        detail=f"'{branch}' already tracks '{remote}/{branch}'.",
                        remote=remote,
                        branch=branch,
                        command_preview=self._command_preview(
                            "git", "branch", "--set-upstream-to", f"{remote}/{branch}", branch
                        ),
                    )
                ],
                explanation=f"'{branch}' already tracks '{remote}/{branch}'.",
            )

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.SET_UPSTREAM,
                    title=f"Set upstream to {remote}/{branch}",
                    detail=(
                        f"Tell Git that local branch '{branch}' should pull from and push to "
                        f"'{remote}/{branch}'. This does not publish commits."
                    ),
                    remote=remote,
                    branch=branch,
                    command_preview=self._command_preview(
                        "git", "branch", "--set-upstream-to", f"{remote}/{branch}", branch
                    ),
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

    def _plan_merge(
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
            return LocalActionPlan(
                matched=True,
                repository_id=repository_id,
                message=message,
                plan_kind=PlanKind.INFO,
                requires_confirmation=False,
                steps=[
                    ActionPlanStep(
                        kind=PlanStepKind.MERGE,
                        title=f"Already on '{branch_name}'",
                        detail="A branch cannot be merged into itself.",
                        branch=branch_name,
                    )
                ],
                explanation=f"Already on '{branch_name}'.",
            )

        if snapshot.staged_changes or snapshot.modified_changes or snapshot.untracked_paths:
            raise ValidationFailure(
                "Merge requires a clean working tree. Commit, stash, or discard local changes first."
            )

        known_branches = {branch.name for branch in snapshot.local_branches}
        if known_branches and branch_name not in known_branches:
            raise ValidationFailure(
                f"Branch '{branch_name}' is not a known local branch. Fetch or create it first."
            )

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.MERGE,
                    title=f"Merge '{branch_name}'",
                    detail=(
                        f"Merge local branch '{branch_name}' into the current branch. "
                        "If conflicts occur, the app will show conflict guidance and block unrelated writes."
                    ),
                    branch=branch_name,
                    command_preview=self._command_preview("git", "merge", "--no-edit", branch_name),
                )
            ],
        )

    def _plan_merge_abort(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
    ) -> LocalActionPlan:
        if not snapshot.write_blocked_reason or (
            "merge" not in snapshot.write_blocked_reason.lower() and not snapshot.conflicts
        ):
            raise ValidationFailure("No merge appears to be in progress.")

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.MERGE_ABORT,
                    title="Abort merge",
                    detail="Return the repository to the pre-merge state with git merge --abort.",
                    command_preview=self._command_preview("git", "merge", "--abort"),
                )
            ],
        )

    def _plan_merge_commit(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
    ) -> LocalActionPlan:
        if snapshot.conflicts:
            raise ValidationFailure("Resolve all conflicted files before continuing the merge.")
        if not snapshot.write_blocked_reason or "merge" not in snapshot.write_blocked_reason.lower():
            raise ValidationFailure("No merge appears to be in progress.")
        if not snapshot.staged_changes:
            raise ValidationFailure("Stage the resolved merge files before continuing the merge.")

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.MERGE_COMMIT,
                    title="Complete merge",
                    detail="Create the merge commit using Git's prepared merge message.",
                    command_preview=self._command_preview("git", "commit", "--no-edit"),
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

        if not snapshot.staged_changes and not snapshot.modified_changes and not snapshot.untracked_paths:
            raise ValidationFailure("There are no local changes to stash.")

        count = len(snapshot.staged_changes) + len(snapshot.modified_changes) + len(snapshot.untracked_paths)
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

    def _plan_stash_apply(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        stash_ref: str,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)
        validated_ref = self._validate_stash_ref(stash_ref)

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.STASH_APPLY,
                    title=f"Apply {validated_ref}",
                    detail=(
                        "Restore this stash entry without removing it from the stash list. "
                        "Execution is blocked if applying the stash would cause conflicts."
                    ),
                    stash_ref=validated_ref,
                    command_preview=self._command_preview("git", "stash", "apply", validated_ref),
                )
            ],
        )

    def _plan_stash_drop(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        stash_ref: str,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)
        validated_ref = self._validate_stash_ref(stash_ref)

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.STASH_DROP,
                    title=f"Drop {validated_ref}",
                    detail=(
                        "DESTRUCTIVE - permanently remove this entry from the stash list. "
                        "The stash contents cannot be restored from the app after this runs."
                    ),
                    stash_ref=validated_ref,
                    command_preview=self._command_preview("git", "stash", "drop", validated_ref),
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

    def _plan_create_tag(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        tag_name: str,
        tag_message: str,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)
        validated_tag = self._validate_tag_name(tag_name)
        validated_message = self._validate_tag_message(tag_message)

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.CREATE_TAG,
                    title=f"Create tag '{validated_tag}'",
                    detail=(
                        f"Create annotated local tag '{validated_tag}' at the current HEAD. "
                        "The tag is not pushed until you explicitly push it."
                    ),
                    commit_message=validated_message,
                    tag_name=validated_tag,
                    command_preview=self._command_preview(
                        "git", "tag", "-a", validated_tag, "-m", validated_message
                    ),
                )
            ],
        )

    def _plan_delete_tag(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        tag_name: str,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)
        validated_tag = self._validate_tag_name(tag_name)

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.DELETE_TAG,
                    title=f"Delete tag '{validated_tag}'",
                    detail=(
                        f"DESTRUCTIVE - delete local tag '{validated_tag}'. "
                        "This does not delete the tag from any remote."
                    ),
                    tag_name=validated_tag,
                    command_preview=self._command_preview("git", "tag", "-d", validated_tag),
                )
            ],
        )

    def _plan_push_tag(
        self,
        repository_id: str,
        message: str,
        snapshot: RepositorySnapshot,
        tag_name: str,
        requested_remote: str | None,
    ) -> LocalActionPlan:
        self._ensure_writes_allowed(snapshot)
        validated_tag = self._validate_tag_name(tag_name)
        remote = self._resolve_tag_remote(requested_remote, snapshot.remote_names)

        return self._write_plan(
            repository_id=repository_id,
            message=message,
            steps=[
                ActionPlanStep(
                    kind=PlanStepKind.PUSH_TAG,
                    title=f"Push tag '{validated_tag}'",
                    detail=(
                        f"Push only tag '{validated_tag}' to remote '{remote}'. "
                        "Other local tags are not published."
                    ),
                    remote=remote,
                    tag_name=validated_tag,
                    command_preview=self._command_preview("git", "push", remote, validated_tag),
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
        include_conflicts: bool = False,
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
            if include_conflicts:
                candidates.extend(snapshot.conflicts)

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
    def _validate_stash_ref(value: str) -> str:
        candidate = value.strip().lower()
        if not _STASH_REF_PATTERN.fullmatch(candidate):
            raise ValidationFailure("Use an explicit stash reference such as stash@{0}.")
        return candidate

    @staticmethod
    def _validate_tag_name(value: str) -> str:
        candidate = value.strip().strip("`'\"").strip().rstrip(".!?")
        if (
            not _TAG_PATTERN.fullmatch(candidate)
            or ".." in candidate
            or "@{" in candidate
            or candidate.endswith(".")
            or candidate.endswith("/")
            or "//" in candidate
            or candidate.startswith("-")
        ):
            raise ValidationFailure(f"'{value}' is not a valid tag name.")
        return candidate

    @staticmethod
    def _validate_tag_message(value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValidationFailure("Tag messages cannot be blank.")
        if "\x00" in candidate or "\n" in candidate or "\r" in candidate:
            raise ValidationFailure("Tag messages must be one line and cannot contain control characters.")
        if len(candidate) > 300:
            raise ValidationFailure("Tag messages must be 300 characters or fewer in v1.")
        return candidate

    @staticmethod
    def _resolve_tag_remote(requested_remote: str | None, remote_names: list[str]) -> str:
        if not remote_names:
            raise ValidationFailure(
                "Tag push is unavailable because no Git remote is configured."
            )

        if requested_remote:
            candidate = requested_remote.strip()
            if candidate not in remote_names:
                raise ValidationFailure(f"Remote '{candidate}' is not configured for this repository.")
            return candidate

        if "origin" in remote_names:
            return "origin"
        if len(remote_names) == 1:
            return remote_names[0]

        names = ", ".join(remote_names)
        raise ValidationFailure(
            f"Multiple remotes are configured ({names}). Specify the target, e.g. 'push tag v0.3.0 to origin'."
        )

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
            "all the changes",
            "all my changes",
            "my changes",
            "the changes",
            "changes",
            "changed files",
            "all changed files",
            "all the files",
            "the files",
            "all files",
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
            ReadAction.GRAPH: "Read commit graph",
            ReadAction.STASHES: "Read stash list",
            ReadAction.STASH_SHOW: "Inspect stash",
            ReadAction.REMOTES: "Read remotes",
            ReadAction.FILE_HISTORY: "Read file history",
            ReadAction.BLAME: "Read file blame",
            ReadAction.CONFLICTS: "Read conflict guidance",
            ReadAction.TAGS: "Read tags",
            ReadAction.TAG_SHOW: "Inspect tag",
            ReadAction.REVIEW_STATUS: "Read PR/MR review status",
        }
        return titles.get(action, "Read local repository state")


class QuotedSegment:
    def __init__(self, *, start: int, end: int, value: str) -> None:
        self.start = start
        self.end = end
        self.value = value
