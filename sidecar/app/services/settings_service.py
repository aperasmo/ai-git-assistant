from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.schemas.settings import (
    GitHubSettings,
    LLMProviderKind,
    LLMSettings,
    UpdateGitHubSettingsRequest,
    UpdateLLMSettingsRequest,
)
from app.services.secret_store import SecretStore

_LEGACY_API_KEY = "llm_api_key"
_ENCRYPTED_API_KEY = "llm_api_key_dpapi"
_ENCRYPTED_GITHUB_TOKEN = "github_token_dpapi"
_LLM_KEYS = ("llm_provider", _LEGACY_API_KEY, _ENCRYPTED_API_KEY, "llm_model", "llm_base_url")


class SettingsService:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._initialise()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialise(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def get_llm_settings(self) -> LLMSettings:
        with self._connection() as conn:
            rows = conn.execute(
                f"SELECT key, value FROM app_settings WHERE key IN ({','.join('?' * len(_LLM_KEYS))})",
                _LLM_KEYS,
            ).fetchall()

        data = {row["key"]: row["value"] for row in rows}
        provider_str = data.get("llm_provider")
        provider: LLMProviderKind | None = None
        if provider_str:
            try:
                provider = LLMProviderKind(provider_str)
            except ValueError:
                pass

        return LLMSettings(
            provider=provider,
            api_key_set=bool(
                data.get(_ENCRYPTED_API_KEY, "").strip()
                or data.get(_LEGACY_API_KEY, "").strip()
            ),
            model=data.get("llm_model") or None,
            base_url=data.get("llm_base_url") or None,
        )

    def get_raw_api_key(self) -> str | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (_ENCRYPTED_API_KEY,),
            ).fetchone()
            legacy_row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (_LEGACY_API_KEY,),
            ).fetchone()

        encrypted = (row["value"] if row else "").strip()
        if encrypted:
            return SecretStore.unprotect(encrypted).strip() or None

        legacy_value = (legacy_row["value"] if legacy_row else "").strip()
        if legacy_value:
            self._store_api_key(legacy_value)
            return legacy_value

        return None

    def api_key_storage_kind(self) -> str:
        return SecretStore.storage_kind()

    def get_github_settings(self) -> GitHubSettings:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (_ENCRYPTED_GITHUB_TOKEN,),
            ).fetchone()

        return GitHubSettings(token_set=bool((row["value"] if row else "").strip()))

    def get_raw_github_token(self) -> str | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (_ENCRYPTED_GITHUB_TOKEN,),
            ).fetchone()

        encrypted = (row["value"] if row else "").strip()
        if not encrypted:
            return None
        return SecretStore.unprotect(encrypted).strip() or None

    def update_github_settings(self, request: UpdateGitHubSettingsRequest) -> GitHubSettings:
        if request.token is not None:
            with self._connection() as conn:
                if request.token.strip():
                    conn.execute(
                        "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                        (_ENCRYPTED_GITHUB_TOKEN, SecretStore.protect(request.token.strip())),
                    )
                else:
                    conn.execute("DELETE FROM app_settings WHERE key = ?", (_ENCRYPTED_GITHUB_TOKEN,))

        return self.get_github_settings()

    def update_llm_settings(self, request: UpdateLLMSettingsRequest) -> LLMSettings:
        updates: list[tuple[str, str]] = []
        deletes: list[str] = []

        if request.provider is not None:
            if request.provider:
                updates.append(("llm_provider", request.provider.value))
            else:
                deletes.append("llm_provider")

        if request.api_key is not None:
            if request.api_key.strip():
                updates.append((_ENCRYPTED_API_KEY, SecretStore.protect(request.api_key.strip())))
                deletes.append(_LEGACY_API_KEY)
            else:
                deletes.extend([_LEGACY_API_KEY, _ENCRYPTED_API_KEY])

        if request.model is not None:
            if request.model.strip():
                updates.append(("llm_model", request.model.strip()))
            else:
                deletes.append("llm_model")

        if request.base_url is not None:
            if request.base_url.strip():
                updates.append(("llm_base_url", request.base_url.strip()))
            else:
                deletes.append("llm_base_url")

        with self._connection() as conn:
            for key, value in updates:
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
            for key in deletes:
                conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))

        return self.get_llm_settings()

    def _store_api_key(self, api_key: str) -> None:
        encrypted = SecretStore.protect(api_key)
        with self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                (_ENCRYPTED_API_KEY, encrypted),
            )
            conn.execute("DELETE FROM app_settings WHERE key = ?", (_LEGACY_API_KEY,))
