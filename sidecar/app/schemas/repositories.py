from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator

from .base import ApiModel


class RegisterRepositoryRequest(ApiModel):
    path: str = Field(min_length=1, max_length=4096)


class InitialiseAndRegisterRequest(RegisterRepositoryRequest):
    # This is a write operation. The client must explicitly opt in before the
    # service can initialise a Git repository in the selected folder.
    confirmed: Literal[True]


class FolderClassificationResponse(ApiModel):
    kind: Literal[
        "existing_repository",
        "nested_repository",
        "initialisation_required",
        "unsupported_repository",
    ]
    selected_path: str
    repository_root: str | None = None
    can_initialise: bool
    message: str | None = None


class RepositoryResponse(ApiModel):
    id: str
    display_name: str
    path_label: str
    current_branch: str | None = None
    external_llm_allowed: bool = False
    last_opened_at: str
    last_remote_refresh_at: str | None = None


class ChangedPath(ApiModel):
    path: str
    index_status: str
    worktree_status: str
    kind: str


class RecentCommit(ApiModel):
    full_hash: str
    short_hash: str
    author: str
    committed_at: str
    subject: str


class BranchInfo(ApiModel):
    name: str
    is_current: bool
    upstream: str | None = None


class RepositorySnapshot(ApiModel):
    repository_id: str
    branch: str | None = None
    head_commit: str | None = None
    upstream_remote: str | None = None
    upstream_branch: str | None = None
    staged_changes: list[ChangedPath] = Field(default_factory=list)
    modified_changes: list[ChangedPath] = Field(default_factory=list)
    untracked_paths: list[ChangedPath] = Field(default_factory=list)
    conflicts: list[ChangedPath] = Field(default_factory=list)
    ahead: int = 0
    behind: int = 0
    remote_last_refreshed_at: str | None = None
    write_blocked_reason: str | None = None
    fingerprint: str
    recent_commits: list[RecentCommit] = Field(default_factory=list)
    remote_names: list[str] = Field(default_factory=list)
    remote_urls: dict[str, str] = Field(default_factory=dict)
    local_branches: list[BranchInfo] = Field(default_factory=list)


class ReadAction(StrEnum):
    STATUS = "status"
    LOG = "log"
    DIFF = "diff"
    BRANCHES = "branches"
    FETCH = "fetch"


class ReadActionRequest(ApiModel):
    action: ReadAction
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def ensure_small_parameter_object(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 4:
            raise ValueError("Too many action parameters.")
        return value


class ReadActionResult(ApiModel):
    action: ReadAction
    title: str
    summary: str
    content: str
    snapshot: RepositorySnapshot


class LocalResolveRequest(ApiModel):
    message: str = Field(min_length=1, max_length=500)


class LocalResolution(ApiModel):
    # Retained for the local read matcher itself. The HTTP route returns the
    # broader LocalActionPlan below so it can describe read and write requests.
    matched: bool
    action: ReadAction | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    explanation: str


class PlanKind(StrEnum):
    READ = "read"
    WRITE = "write"
    INFO = "info"

class PlanStepKind(StrEnum):
    READ = "read"
    STAGE = "stage"
    COMMIT = "commit"
    PUSH = "push"
    PULL = "pull"
    UNSTAGE = "unstage"
    DISCARD = "discard"
    SWITCH = "switch"
    CREATE_BRANCH = "create_branch"
    STASH = "stash"
    STASH_POP = "stash_pop"
    DELETE_BRANCH = "delete_branch"
    ADD_REMOTE = "add_remote"
    RENAME_BRANCH = "rename_branch"


class ActionPlanStep(ApiModel):
    kind: PlanStepKind
    title: str
    detail: str
    paths: list[str] = Field(default_factory=list)
    commit_message: str | None = None
    remote: str | None = None
    branch: str | None = None
    remote_url: str | None = None
    command_preview: str | None = None
    ahead: int | None = None
    behind: int | None = None
    force: bool | None = None
    set_upstream: bool = False

class LocalActionPlan(ApiModel):
    matched: bool
    repository_id: str
    message: str
    plan_kind: PlanKind | None = None
    requires_confirmation: bool = False
    plan_id: str | None = None
    read_action: ReadAction | None = None
    read_params: dict[str, Any] = Field(default_factory=dict)
    steps: list[ActionPlanStep] = Field(default_factory=list)
    explanation: str
    source: str = "local"


class AddToGitignoreRequest(ApiModel):
    paths: list[str]


class SubmitPlanRequest(ApiModel):
    steps: list[ActionPlanStep]
    explanation: str = "Wizard-submitted plan"


class SubmitPlanResponse(ApiModel):
    plan_id: str


class CloneRepositoryRequest(ApiModel):
    url: str
    parent_path: str
    folder_name: str | None = None


class ExecuteActionPlanRequest(ApiModel):
    plan_id: str = Field(min_length=1, max_length=128)


class ActionExecutionResult(ApiModel):
    plan_id: str
    title: str
    summary: str
    content: str
    snapshot: RepositorySnapshot


class CancelActionPlanResponse(ApiModel):
    cancelled: bool


class SetExternalLLMRequest(ApiModel):
    allowed: bool
