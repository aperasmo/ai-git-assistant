from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.auth import require_session_token
from app.llm.router import LLMNotConfiguredError, _build_provider
from app.schemas.settings import LLMSettings, UpdateLLMSettingsRequest

router = APIRouter(prefix="/v1/settings", tags=["settings"])


class LLMTestResult(BaseModel):
    ok: bool
    message: str


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


@router.post(
    "/llm/test",
    response_model=LLMTestResult,
    dependencies=[Depends(require_session_token)],
)
def test_llm_connection(request: Request) -> LLMTestResult:
    svc = _settings_service(request)
    try:
        provider = _build_provider(svc)
        provider.ping()
        settings = svc.get_llm_settings()
        model = settings.model or "default model"
        return LLMTestResult(ok=True, message=f"Connected successfully using {model}.")
    except LLMNotConfiguredError as exc:
        return LLMTestResult(ok=False, message=str(exc))
    except Exception as exc:
        return LLMTestResult(ok=False, message=f"Connection failed: {exc}")
