from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class AppError(Exception):
    message: str
    status_code: int = 400
    code: str = "application_error"


class NotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=404, code="not_found")


class ValidationFailure(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=422, code="validation_failure")


class GitCommandError(AppError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message=message, status_code=status_code, code="git_command_failed")


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )
