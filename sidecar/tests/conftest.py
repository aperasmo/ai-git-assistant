from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("GIT_CEILING_DIRECTORIES", str(PROJECT_ROOT))


@pytest.fixture()
def git_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "demo-repository"
    repository.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repository,
            check=True,
            shell=False,
            capture_output=True,
            text=True,
        )

    git("init")
    git("config", "user.name", "Test User")
    git("config", "user.email", "test@example.invalid")
    (repository / "README.md").write_text("# Demo\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "Initial commit")
    (repository / "README.md").write_text("# Demo\n\nChanged.\n", encoding="utf-8")
    return repository


@pytest.fixture()
def git_repository_with_remote(tmp_path: Path) -> Path:
    """A cloned repository whose main branch already tracks origin/main."""
    bare = tmp_path / "remote.git"
    bare.mkdir()
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)

    repository = tmp_path / "demo-repository"
    subprocess.run(["git", "clone", str(bare), str(repository)], check=True, capture_output=True)

    def git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repository,
            check=True,
            shell=False,
            capture_output=True,
            text=True,
        )

    git("config", "user.name", "Test User")
    git("config", "user.email", "test@example.invalid")
    (repository / "login.py").write_text("# login stub\n", encoding="utf-8")
    return repository


@pytest.fixture()
def git_repository_behind_remote(tmp_path: Path) -> Path:
    """A cloned repo where origin/main is 1 commit ahead (local is behind)."""
    bare = tmp_path / "remote.git"
    bare.mkdir()
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)

    contrib = tmp_path / "contrib"
    subprocess.run(["git", "clone", str(bare), str(contrib)], check=True, capture_output=True)
    for args in [["git", "config", "user.name", "Contributor"], ["git", "config", "user.email", "c@test.invalid"]]:
        subprocess.run(args, cwd=contrib, check=True, capture_output=True)
    (contrib / "first.txt").write_text("first\n")
    subprocess.run(["git", "add", "first.txt"], cwd=contrib, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "first commit"], cwd=contrib, check=True, capture_output=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=contrib, check=True, capture_output=True)

    repository = tmp_path / "our-repo"
    subprocess.run(["git", "clone", str(bare), str(repository)], check=True, capture_output=True)
    for args in [["git", "config", "user.name", "Test User"], ["git", "config", "user.email", "test@test.invalid"]]:
        subprocess.run(args, cwd=repository, check=True, capture_output=True)

    # contributor pushes a second commit; our clone doesn't have it yet
    (contrib / "second.txt").write_text("second\n")
    subprocess.run(["git", "add", "second.txt"], cwd=contrib, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "second commit"], cwd=contrib, check=True, capture_output=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=contrib, check=True, capture_output=True)

    # fetch so our tracking ref knows about it (behind=1, ahead=0)
    subprocess.run(["git", "fetch"], cwd=repository, check=True, capture_output=True)
    return repository


@pytest.fixture()
def app_client(tmp_path: Path) -> TestClient:
    token = "test-token-" + "x" * 48
    settings = Settings(
        session_token=token,
        environment="test",
        database_path=tmp_path / "test.db",
        initial_branch="main",
    )
    app = create_app(settings)
    return TestClient(app)


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token-" + "x" * 48}
