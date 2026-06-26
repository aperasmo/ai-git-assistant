from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

from app.git.repository_inspector import display_path_label, utc_now_iso
from app.schemas.repositories import RepositoryResponse


class RepositoryStore:
    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        self._initialise()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialise(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS repositories (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    canonical_path TEXT NOT NULL UNIQUE,
                    path_label TEXT NOT NULL,
                    current_branch TEXT,
                    external_llm_allowed INTEGER NOT NULL DEFAULT 0,
                    last_opened_at TEXT NOT NULL,
                    last_remote_refresh_at TEXT
                )
                """
            )

    def upsert(
        self,
        canonical_path: Path,
        *,
        current_branch: str | None,
    ) -> RepositoryResponse:
        timestamp = utc_now_iso()
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT * FROM repositories WHERE canonical_path = ?",
                (str(canonical_path),),
            ).fetchone()

            if existing:
                connection.execute(
                    """
                    UPDATE repositories
                    SET display_name = ?, path_label = ?, current_branch = ?, last_opened_at = ?
                    WHERE id = ?
                    """,
                    (
                        canonical_path.name,
                        display_path_label(canonical_path),
                        current_branch,
                        timestamp,
                        existing["id"],
                    ),
                )
                repository_id = existing["id"]
            else:
                repository_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO repositories (
                        id, display_name, canonical_path, path_label, current_branch,
                        external_llm_allowed, last_opened_at
                    ) VALUES (?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        repository_id,
                        canonical_path.name,
                        str(canonical_path),
                        display_path_label(canonical_path),
                        current_branch,
                        timestamp,
                    ),
                )

        return self.get(repository_id)

    def list(self) -> list[RepositoryResponse]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM repositories ORDER BY last_opened_at DESC"
            ).fetchall()
        return [self._to_response(row) for row in rows]

    def get(self, repository_id: str) -> RepositoryResponse:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM repositories WHERE id = ?",
                (repository_id,),
            ).fetchone()
        if row is None:
            from app.errors import NotFoundError

            raise NotFoundError("Repository was not found.")
        return self._to_response(row)

    def remove(self, repository_id: str) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM repositories WHERE id = ?", (repository_id,))

    def update_external_llm_allowed(self, repository_id: str, allowed: bool) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE repositories SET external_llm_allowed = ? WHERE id = ?",
                (1 if allowed else 0, repository_id),
            )

    def canonical_path(self, repository_id: str) -> Path:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT canonical_path FROM repositories WHERE id = ?",
                (repository_id,),
            ).fetchone()
        if row is None:
            from app.errors import NotFoundError

            raise NotFoundError("Repository was not found.")
        return Path(row["canonical_path"])

    def update_inspection(
        self,
        repository_id: str,
        *,
        branch: str | None,
        remote_last_refreshed_at: str | None = None,
        update_remote_refresh: bool = False,
    ) -> None:
        with self._connection() as connection:
            if update_remote_refresh:
                connection.execute(
                    """
                    UPDATE repositories
                    SET current_branch = ?, last_opened_at = ?, last_remote_refresh_at = ?
                    WHERE id = ?
                    """,
                    (branch, utc_now_iso(), remote_last_refreshed_at, repository_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE repositories
                    SET current_branch = ?, last_opened_at = ?
                    WHERE id = ?
                    """,
                    (branch, utc_now_iso(), repository_id),
                )

    @staticmethod
    def _to_response(row: sqlite3.Row) -> RepositoryResponse:
        return RepositoryResponse(
            id=row["id"],
            display_name=row["display_name"],
            path_label=row["path_label"],
            current_branch=row["current_branch"],
            external_llm_allowed=bool(row["external_llm_allowed"]),
            last_opened_at=row["last_opened_at"],
            last_remote_refresh_at=row["last_remote_refresh_at"],
        )
