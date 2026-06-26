from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    session_token: str
    environment: str
    database_path: Path
    initial_branch: str

    @classmethod
    def from_env(cls) -> Settings:
        token = os.getenv("AIGA_SESSION_TOKEN", "")
        if len(token) < 32:
            raise RuntimeError(
                
                    "AIGA_SESSION_TOKEN must be provided by the desktop shell and "
                    "contain at least 32 characters."
                
            )

        database = Path(
            os.getenv(
                "AIGA_DATABASE_PATH",
                str(Path.home() / ".ai-git-assistant" / "ai-git-assistant.db"),
            )
        ).expanduser()

        # Repository initialisation is a write operation. Keep its branch policy
        # in configuration rather than embedding it in the service layer.
        initial_branch = os.getenv("AIGA_INITIAL_BRANCH", "main").strip()

        if not initial_branch:
            raise RuntimeError("AIGA_INITIAL_BRANCH must not be blank.")

        return cls(
            session_token=token,
            environment=os.getenv("AIGA_ENV", "development"),
            database_path=database,
            initial_branch=initial_branch,
        )
