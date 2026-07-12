from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.auth import require_session_token
from app.schemas.repositories import (
    ActionExecutionResult,
    AddToGitignoreRequest,
    AgentSessionActionResponse,
    AgentSessionComparisonResponse,
    AgentSessionResponse,
    CancelActionPlanResponse,
    CloneRepositoryRequest,
    CreateAgentSessionRequest,
    DraftGitHubPullRequestRequest,
    DraftGitHubPullRequestResponse,
    DraftGitHubReleaseRequest,
    DraftGitHubReleaseResponse,
    ExecuteActionPlanRequest,
    FolderClassificationResponse,
    GenerateChangeSummaryRequest,
    GenerateChangeSummaryResponse,
    GenerateCommitMessageRequest,
    GenerateCommitMessageResponse,
    InitialiseAndRegisterRequest,
    LocalActionPlan,
    LocalResolveRequest,
    ReadActionRequest,
    ReadActionResult,
    RegisterRepositoryRequest,
    RepositoryResponse,
    RepositorySnapshot,
    SetExternalLLMRequest,
    SubmitPlanRequest,
    SubmitPlanResponse,
)

router = APIRouter(prefix="/v1/repositories", tags=["repositories"])


def _service(request: Request):
    return request.app.state.repository_service


@router.post(
    "/classify",
    response_model=FolderClassificationResponse,
    dependencies=[Depends(require_session_token)],
)
def classify_repository_folder(
    payload: RegisterRepositoryRequest,
    request: Request,
) -> FolderClassificationResponse:
    return _service(request).classify_selected_folder(payload.path)


@router.post(
    "/initialise-and-register",
    response_model=RepositoryResponse,
    dependencies=[Depends(require_session_token)],
)
def initialise_and_register_repository(
    payload: InitialiseAndRegisterRequest,
    request: Request,
) -> RepositoryResponse:
    return _service(request).initialise_and_register(payload.path)


@router.post(
    "/register",
    response_model=RepositoryResponse,
    dependencies=[Depends(require_session_token)],
)
def register_repository(
    payload: RegisterRepositoryRequest,
    request: Request,
) -> RepositoryResponse:
    return _service(request).register(payload.path)


@router.post(
    "/clone",
    response_model=RepositoryResponse,
    dependencies=[Depends(require_session_token)],
)
def clone_repository(
    payload: CloneRepositoryRequest,
    request: Request,
) -> RepositoryResponse:
    return _service(request).clone_repository(payload.url, payload.parent_path, payload.folder_name)


@router.delete(
    "/{repository_id}",
    status_code=204,
    dependencies=[Depends(require_session_token)],
)
def remove_repository(repository_id: str, request: Request) -> None:
    _service(request).remove_repository(repository_id)


@router.get(
    "",
    response_model=list[RepositoryResponse],
    dependencies=[Depends(require_session_token)],
)
def list_repositories(request: Request) -> list[RepositoryResponse]:
    return _service(request).list()


@router.get(
    "/{repository_id}/snapshot",
    response_model=RepositorySnapshot,
    dependencies=[Depends(require_session_token)],
)
def repository_snapshot(repository_id: str, request: Request) -> RepositorySnapshot:
    return _service(request).snapshot(repository_id)


@router.get(
    "/{repository_id}/agent-sessions",
    response_model=list[AgentSessionResponse],
    dependencies=[Depends(require_session_token)],
)
def list_agent_sessions(repository_id: str, request: Request) -> list[AgentSessionResponse]:
    return _service(request).list_agent_sessions(repository_id)


@router.post(
    "/{repository_id}/agent-sessions",
    response_model=AgentSessionResponse,
    dependencies=[Depends(require_session_token)],
)
def create_agent_session(
    repository_id: str,
    payload: CreateAgentSessionRequest,
    request: Request,
) -> AgentSessionResponse:
    return _service(request).create_agent_session(
        repository_id,
        task=payload.task,
        branch_name=payload.branch_name,
        base_branch=payload.base_branch,
    )


@router.get(
    "/{repository_id}/agent-sessions/{session_id}/compare",
    response_model=AgentSessionComparisonResponse,
    dependencies=[Depends(require_session_token)],
)
def compare_agent_session(
    repository_id: str,
    session_id: str,
    request: Request,
) -> AgentSessionComparisonResponse:
    return _service(request).compare_agent_session(repository_id, session_id)


@router.post(
    "/{repository_id}/agent-sessions/{session_id}/merge",
    response_model=AgentSessionActionResponse,
    dependencies=[Depends(require_session_token)],
)
def merge_agent_session(
    repository_id: str,
    session_id: str,
    request: Request,
) -> AgentSessionActionResponse:
    return _service(request).merge_agent_session(repository_id, session_id)


@router.post(
    "/{repository_id}/agent-sessions/{session_id}/abandon",
    response_model=AgentSessionActionResponse,
    dependencies=[Depends(require_session_token)],
)
def abandon_agent_session(
    repository_id: str,
    session_id: str,
    request: Request,
) -> AgentSessionActionResponse:
    return _service(request).abandon_agent_session(repository_id, session_id)


@router.post(
    "/{repository_id}/agent-sessions/{session_id}/cleanup",
    response_model=AgentSessionActionResponse,
    dependencies=[Depends(require_session_token)],
)
def cleanup_agent_session(
    repository_id: str,
    session_id: str,
    request: Request,
) -> AgentSessionActionResponse:
    return _service(request).cleanup_agent_session(repository_id, session_id)


@router.post(
    "/{repository_id}/read-actions",
    response_model=ReadActionResult,
    dependencies=[Depends(require_session_token)],
)
def run_read_action(
    repository_id: str,
    payload: ReadActionRequest,
    request: Request,
) -> ReadActionResult:
    return _service(request).run_read_action(repository_id, payload)


@router.post(
    "/{repository_id}/resolve-local",
    response_model=LocalActionPlan,
    dependencies=[Depends(require_session_token)],
)
def resolve_local(
    repository_id: str,
    payload: LocalResolveRequest,
    request: Request,
) -> LocalActionPlan:
    # The route name is retained for compatibility. It now creates a bounded
    # local action plan for either an existing read request or an approved write
    # request; no Git write runs at this stage.
    return _service(request).plan_local_request(repository_id, payload.message)


@router.post(
    "/{repository_id}/execute-plan",
    response_model=ActionExecutionResult,
    dependencies=[Depends(require_session_token)],
)
def execute_action_plan(
    repository_id: str,
    payload: ExecuteActionPlanRequest,
    request: Request,
) -> ActionExecutionResult:
    return _service(request).execute_action_plan(repository_id, payload.plan_id)


@router.post(
    "/{repository_id}/submit-plan",
    response_model=SubmitPlanResponse,
    dependencies=[Depends(require_session_token)],
)
def submit_wizard_plan(
    repository_id: str,
    payload: SubmitPlanRequest,
    request: Request,
) -> SubmitPlanResponse:
    plan_id = _service(request).submit_wizard_plan(repository_id, payload.steps)
    return SubmitPlanResponse(plan_id=plan_id)


@router.post(
    "/{repository_id}/generate-commit-message",
    response_model=GenerateCommitMessageResponse,
    dependencies=[Depends(require_session_token)],
)
def generate_commit_message(
    repository_id: str,
    payload: GenerateCommitMessageRequest,
    request: Request,
) -> GenerateCommitMessageResponse:
    return _service(request).generate_commit_message(repository_id, payload.paths, payload.style)


@router.post(
    "/{repository_id}/generate-change-summary",
    response_model=GenerateChangeSummaryResponse,
    dependencies=[Depends(require_session_token)],
)
def generate_change_summary(
    repository_id: str,
    payload: GenerateChangeSummaryRequest,
    request: Request,
) -> GenerateChangeSummaryResponse:
    return _service(request).generate_change_summary(repository_id, payload.paths)


@router.post(
    "/{repository_id}/github/releases/draft",
    response_model=DraftGitHubReleaseResponse,
    dependencies=[Depends(require_session_token)],
)
def draft_github_release(
    repository_id: str,
    payload: DraftGitHubReleaseRequest,
    request: Request,
) -> DraftGitHubReleaseResponse:
    return _service(request).draft_github_release(repository_id, payload)


@router.post(
    "/{repository_id}/github/pull-requests/draft",
    response_model=DraftGitHubPullRequestResponse,
    dependencies=[Depends(require_session_token)],
)
def draft_github_pull_request(
    repository_id: str,
    payload: DraftGitHubPullRequestRequest,
    request: Request,
) -> DraftGitHubPullRequestResponse:
    return _service(request).draft_github_pull_request(repository_id, payload)


@router.post(
    "/{repository_id}/cancel-plan",
    response_model=CancelActionPlanResponse,
    dependencies=[Depends(require_session_token)],
)
def cancel_action_plan(
    repository_id: str,
    payload: ExecuteActionPlanRequest,
    request: Request,
) -> CancelActionPlanResponse:
    return _service(request).cancel_action_plan(repository_id, payload.plan_id)


@router.post(
    "/{repository_id}/add-to-gitignore",
    dependencies=[Depends(require_session_token)],
)
def add_to_gitignore(
    repository_id: str,
    payload: AddToGitignoreRequest,
    request: Request,
) -> dict:
    _service(request).add_to_gitignore(repository_id, payload.paths)
    return {"ok": True}


@router.post(
    "/{repository_id}/set-llm",
    response_model=RepositoryResponse,
    dependencies=[Depends(require_session_token)],
)
def set_external_llm_allowed(
    repository_id: str,
    payload: SetExternalLLMRequest,
    request: Request,
) -> RepositoryResponse:
    return _service(request).set_external_llm_allowed(repository_id, payload.allowed)
