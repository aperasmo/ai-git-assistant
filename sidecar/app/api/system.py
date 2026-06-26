from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.auth import require_session_token
from app.git.client import GitClient
from app.schemas.system import GitInstallationResponse

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
