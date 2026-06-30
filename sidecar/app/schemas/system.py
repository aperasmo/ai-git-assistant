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


class DiagnosticsResponse(ApiModel):
    app_version: str
    environment: str
    protocol_version: str
    database_path: str
    database_exists: bool
    repository_count: int
    git_status: str
    git_version: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key_set: bool
    api_key_storage: str
    generated_at: str
