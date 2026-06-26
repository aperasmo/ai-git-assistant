from __future__ import annotations

from .base import ApiModel


class HealthResponse(ApiModel):
    status: str
    protocol_version: str
    service_version: str


class GitInstallationResponse(ApiModel):
    status: str
    version: str | None = None
    message: str
