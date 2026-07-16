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


AgentSessionStatus = Literal["active", "merged", "abandoned", "cleaned", "error"]


class CreateAgentSessionRequest(ApiModel):
    task: str = Field(min_length=1, max_length=300)
    branch_name: str | None = Field(default=None, max_length=120)
    base_branch: str | None = Field(default=None, max_length=120)


class AgentSessionResponse(ApiModel):
    id: str
    repository_id: str
    task: str
    branch_name: str
    base_branch: str
    worktree_path: str
    status: AgentSessionStatus
    changed_file_count: int = 0
    commits_ahead: int = 0
    last_commit: str | None = None
    created_at: str
    updated_at: str


class AgentSessionComparisonResponse(ApiModel):
    session: AgentSessionResponse
    title: str
    summary: str
    content: str


class AgentSessionActionResponse(ApiModel):
    session: AgentSessionResponse
    title: str
    summary: str
    content: str


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


class RemoteProviderInfo(ApiModel):
    remote: str
    provider: Literal["github", "gitlab", "bitbucket", "azure_devops", "unknown"]
    label: str
    host: str | None = None
    url: str | None = None


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
    remote_providers: list[RemoteProviderInfo] = Field(default_factory=list)
    local_branches: list[BranchInfo] = Field(default_factory=list)


class ReadAction(StrEnum):
    STATUS = "status"
    LOG = "log"
    DIFF = "diff"
    BRANCHES = "branches"
    FETCH = "fetch"
    GRAPH = "graph"
    STASHES = "stashes"
    STASH_SHOW = "stash_show"
    REMOTES = "remotes"
    FILE_HISTORY = "file_history"
    BLAME = "blame"
    CONFLICTS = "conflicts"
    TAGS = "tags"
    TAG_SHOW = "tag_show"
    REVIEW_STATUS = "review_status"


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
    content_kind: Literal["text", "diff", "graph"] = "text"
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
    SET_UPSTREAM = "set_upstream"
    UNSTAGE = "unstage"
    DISCARD = "discard"
    SWITCH = "switch"
    CREATE_BRANCH = "create_branch"
    STASH = "stash"
    STASH_POP = "stash_pop"
    STASH_APPLY = "stash_apply"
    STASH_DROP = "stash_drop"
    MERGE = "merge"
    MERGE_ABORT = "merge_abort"
    MERGE_COMMIT = "merge_commit"
    CREATE_TAG = "create_tag"
    DELETE_TAG = "delete_tag"
    PUSH_TAG = "push_tag"
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
    stash_ref: str | None = None
    tag_name: str | None = None
    command_preview: str | None = None
    ahead: int | None = None
    behind: int | None = None
    force: bool | None = None
    set_upstream: bool = False


class PlanRisk(ApiModel):
    level: Literal["low", "medium", "high"]
    score: int = Field(ge=0, le=100)
    summary: str
    reasons: list[str] = Field(default_factory=list)


class PrivacyReceipt(ApiModel):
    external_provider: bool
    purpose: str
    provider: str | None = None
    model: str | None = None
    context_items: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    character_count: int = 0
    truncated: bool = False
    exact_context: str | None = None


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
    risk: PlanRisk | None = None
    privacy_receipt: PrivacyReceipt | None = None


class AddToGitignoreRequest(ApiModel):
    paths: list[str]


class SubmitPlanRequest(ApiModel):
    steps: list[ActionPlanStep]
    explanation: str = "Wizard-submitted plan"


class SubmitPlanResponse(ApiModel):
    plan_id: str


CommitMessageStyle = Literal["concise", "detailed", "conventional", "release_ready"]


class GenerateCommitMessageRequest(ApiModel):
    paths: list[str] = Field(default_factory=list, max_length=100)
    style: CommitMessageStyle = "detailed"


class GenerateCommitMessageResponse(ApiModel):
    message: str
    subject: str
    body: list[str] = Field(default_factory=list)
    warning: str | None = None
    style: CommitMessageStyle = "detailed"
    confidence: Literal["low", "medium", "high"] = "medium"
    detected_scope: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    source: str = "llm"
    context_summary: str
    privacy_receipt: PrivacyReceipt | None = None


class GenerateChangeSummaryRequest(ApiModel):
    paths: list[str] = Field(default_factory=list, max_length=100)


class CommitSuggestion(ApiModel):
    message: str
    files: list[str] = Field(default_factory=list)
    rationale: str = ""


class GenerateChangeSummaryResponse(ApiModel):
    branch_summary: str
    file_summaries: list[str] = Field(default_factory=list)
    pr_title: str
    pr_body: str
    commit_suggestions: list[CommitSuggestion] = Field(default_factory=list)
    source: str = "llm"
    context_summary: str
    privacy_receipt: PrivacyReceipt | None = None


class DraftGitHubReleaseRequest(ApiModel):
    tag_name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(default="", max_length=20_000)
    asset_path: str | None = Field(default=None, max_length=4096)
    prerelease: bool = False


class DraftGitHubReleaseResponse(ApiModel):
    tag_name: str
    repository: str
    release_url: str
    asset_url: str | None = None
    asset_name: str | None = None
    asset_sha256: str | None = None
    title: str
    summary: str
    content: str
    snapshot: RepositorySnapshot


class DraftGitHubPullRequestRequest(ApiModel):
    base_branch: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(default="", max_length=20_000)


class DraftGitHubPullRequestResponse(ApiModel):
    repository: str
    pull_request_url: str
    number: int
    base_branch: str
    head_branch: str
    provider: Literal["github"] = "github"
    title: str
    summary: str
    content: str
    snapshot: RepositorySnapshot


class DraftGitLabMergeRequestRequest(ApiModel):
    base_branch: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(default="", max_length=20_000)


class DraftGitLabMergeRequestResponse(ApiModel):
    repository: str
    merge_request_url: str
    number: int
    base_branch: str
    head_branch: str
    provider: Literal["gitlab"] = "gitlab"
    title: str
    summary: str
    content: str
    snapshot: RepositorySnapshot


class GeneratePullRequestDraftRequest(ApiModel):
    base_branch: str = Field(min_length=1, max_length=255)


class GeneratePullRequestDraftResponse(ApiModel):
    title: str
    body: str
    checklist: list[str] = Field(default_factory=list)
    branch_summary: str
    file_summaries: list[str] = Field(default_factory=list)
    source: str = "llm"
    context_summary: str
    privacy_receipt: PrivacyReceipt | None = None


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
