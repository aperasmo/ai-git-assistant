from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.auth import require_session_token
from app.schemas.settings import LLMSettings, UpdateLLMSettingsRequest

router = APIRouter(prefix="/v1/settings", tags=["settings"])


def _settings_service(request: Request):
    return request.app.state.settings_service


@router.get(
    "/llm",
    response_model=LLMSettings,
    dependencies=[Depends(require_session_token)],
)
def get_llm_settings(request: Request) -> LLMSettings:
    return _settings_service(request).get_llm_settings()


@router.put(
    "/llm",
    response_model=LLMSettings,
    dependencies=[Depends(require_session_token)],
)
def update_llm_settings(
    payload: UpdateLLMSettingsRequest,
    request: Request,
) -> LLMSettings:
    return _settings_service(request).update_llm_settings(payload)
