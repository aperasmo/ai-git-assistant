from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, Request, status


def require_session_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    settings = request.app.state.settings

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing local session authentication.",
        )

    supplied_token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied_token, settings.session_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid local session authentication.",
        )
