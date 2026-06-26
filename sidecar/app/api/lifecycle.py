from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.auth import require_session_token

router = APIRouter(prefix="/v1", tags=["lifecycle"])


@router.post("/shutdown", dependencies=[Depends(require_session_token)])
def shutdown(request: Request) -> dict[str, str]:
    request.app.state.shutdown_requested = True
    return {"status": "accepted"}
