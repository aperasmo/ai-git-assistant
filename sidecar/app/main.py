from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import health, lifecycle, repositories, system
from app.api import settings as settings_routes
from app.config import Settings
from app.errors import AppError, app_error_handler
from app.git.repository_inspector import RepositoryInspector
from app.intent.local_matcher import LocalIntentMatcher
from app.services.repository_service import RepositoryService
from app.services.repository_store import RepositoryStore
from app.services.settings_service import SettingsService


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(
        title="AI Git Assistant Local Sidecar",
        version="0.4.4",
        docs_url="/docs" if settings.environment == "development" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment == "development" else None,
    )

    store = RepositoryStore(settings.database_path)
    svc_settings = SettingsService(settings.database_path)
    app.state.settings = settings
    app.state.settings_service = svc_settings
    app.state.repository_service = RepositoryService(
        store=store,
        inspector=RepositoryInspector(),
        matcher=LocalIntentMatcher(),
        settings=settings,
        settings_service=svc_settings,
    )
    app.state.shutdown_requested = False

    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(health.router)
    app.include_router(system.router)
    app.include_router(repositories.router)
    app.include_router(settings_routes.router)
    app.include_router(lifecycle.router)

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("aiga.sidecar").exception("Unexpected sidecar error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "The local service could not complete the request. Check the local log.",
                "code": "unexpected_error",
            },
        )

    return app
