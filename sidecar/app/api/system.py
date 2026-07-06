from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from app.auth import require_session_token
from app.git.client import GitClient
from app.schemas.system import DiagnosticsResponse, GitInstallationResponse

router = APIRouter(prefix="/v1/system", tags=["system"])


@router.get(
    "/git-installation",
    response_model=GitInstallationResponse,
    dependencies=[Depends(require_session_token)],
)
def git_installation(request: Request) -> GitInstallationResponse:
    _ = request
    try:
        version = GitClient().version()
    except Exception:
        return GitInstallationResponse(
            status="missing",
            message="Git was not found. Install Git for Windows, then restart AI Git Assistant.",
        )

    return GitInstallationResponse(status="available", version=version, message="Git is available.")


@router.get(
    "/diagnostics",
    response_model=DiagnosticsResponse,
    dependencies=[Depends(require_session_token)],
)
def diagnostics(request: Request) -> DiagnosticsResponse:
    settings = request.app.state.settings
    settings_service = request.app.state.settings_service
    repository_service = request.app.state.repository_service
    llm_settings = settings_service.get_llm_settings()

    try:
        git_version = GitClient().version()
        git_status = "available"
    except Exception:
        git_version = None
        git_status = "missing"

    try:
        repository_count = len(repository_service.list())
    except Exception:
        repository_count = 0

    return DiagnosticsResponse(
        app_version="0.5.0",
        environment=settings.environment,
        protocol_version="1",
        database_path=str(settings.database_path),
        database_exists=settings.database_path.exists(),
        repository_count=repository_count,
        git_status=git_status,
        git_version=git_version,
        llm_provider=llm_settings.provider.value if llm_settings.provider else None,
        llm_model=llm_settings.model,
        llm_api_key_set=llm_settings.api_key_set,
        api_key_storage=settings_service.api_key_storage_kind(),
        generated_at=datetime.now(UTC).isoformat(),
    )
