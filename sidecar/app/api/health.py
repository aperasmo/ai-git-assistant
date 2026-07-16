from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import require_session_token
from app.schemas.system import HealthResponse

router = APIRouter(prefix="/v1", tags=["system"])


@router.get("/health", response_model=HealthResponse, dependencies=[Depends(require_session_token)])
def health() -> HealthResponse:
    return HealthResponse(status="ok", protocol_version="1", service_version="0.7.7")
