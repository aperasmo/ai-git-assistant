from __future__ import annotations

import pytest

from app.errors import ValidationFailure
from app.llm.validator import validate_llm_steps
from app.schemas.repositories import ChangedPath, RepositorySnapshot


def make_snapshot(
    *,
    staged: list[str] | None = None,
    modified: list[str] | None = None,
    untracked: list[str] | None = None,
    remotes: list[str] | None = None,
) -> RepositorySnapshot:
    def _cp(path: str, kind: str) -> ChangedPath:
        return ChangedPath(path=path, index_status="M", worktree_status=" ", kind=kind)

    return RepositorySnapshot(
        repository_id="repo-1",
        branch="main",
        head_commit="abc123",
        upstream_remote="origin",
        upstream_branch="origin/main",
        staged_changes=[_cp(p, "staged") for p in (staged or [])],
        modified_changes=[_cp(p, "modified") for p in (modified or [])],
        untracked_paths=[_cp(p, "untracked") for p in (untracked or [])],
        conflicts=[],
        ahead=0,
        behind=0,
        fingerprint="fp",
        remote_names=remotes if remotes is not None else ["origin"],
    )


def test_valid_stage_step_passes():
    snapshot = make_snapshot(modified=["src/login.py"])
    steps = [{"kind": "stage", "title": "Stage", "detail": "d", "paths": ["src/login.py"]}]
    result = validate_llm_steps(steps, snapshot)
    assert result[0].kind.value == "stage"
    assert result[0].paths == ["src/login.py"]


def test_valid_commit_step_requires_message():
    snapshot = make_snapshot(staged=["src/login.py"])
    steps = [{"kind": "commit", "title": "Commit", "detail": "d", "commit_message": "Fix login"}]
    result = validate_llm_steps(steps, snapshot)
    assert result[0].commit_message == "Fix login"


def test_commit_without_message_raises():
    snapshot = make_snapshot()
    steps = [{"kind": "commit", "title": "Commit", "detail": "d"}]
    with pytest.raises(ValidationFailure, match="without a commit message"):
        validate_llm_steps(steps, snapshot)


def test_unknown_kind_raises():
    snapshot = make_snapshot()
    steps = [{"kind": "force_push", "title": "Bad", "detail": "d"}]
    with pytest.raises(ValidationFailure, match="unsupported"):
        validate_llm_steps(steps, snapshot)


def test_wildcard_path_rejected():
    snapshot = make_snapshot(modified=["src/login.py"])
    for bad_path in [".", "*", "all", "**"]:
        steps = [{"kind": "stage", "title": "Stage", "detail": "d", "paths": [bad_path]}]
        with pytest.raises(ValidationFailure, match="wildcard"):
            validate_llm_steps(steps, snapshot)


def test_path_not_in_changed_files_rejected():
    snapshot = make_snapshot(modified=["src/login.py"])
    steps = [{"kind": "stage", "title": "Stage", "detail": "d", "paths": ["src/nonexistent.py"]}]
    with pytest.raises(ValidationFailure, match="not in the repository"):
        validate_llm_steps(steps, snapshot)


def test_unknown_remote_rejected():
    snapshot = make_snapshot(remotes=["origin"])
    steps = [{"kind": "push", "title": "Push", "detail": "d", "remote": "upstream", "branch": "main"}]
    with pytest.raises(ValidationFailure, match="unknown remote"):
        validate_llm_steps(steps, snapshot)


def test_empty_steps_raises():
    with pytest.raises(ValidationFailure, match="empty"):
        validate_llm_steps([], make_snapshot())


def test_too_many_steps_raises():
    snapshot = make_snapshot()
    steps = [{"kind": "stash_pop", "title": "Pop", "detail": "d"}] * 9
    with pytest.raises(ValidationFailure, match="too many"):
        validate_llm_steps(steps, snapshot)


def test_set_upstream_propagated():
    snapshot = make_snapshot(remotes=["origin"])
    steps = [
        {
            "kind": "push",
            "title": "Push",
            "detail": "d",
            "remote": "origin",
            "branch": "main",
            "set_upstream": True,
        }
    ]
    result = validate_llm_steps(steps, snapshot)
    assert result[0].set_upstream is True


def test_stage_step_requires_paths():
    snapshot = make_snapshot(modified=["src/login.py"])
    steps = [{"kind": "stage", "title": "Stage", "detail": "d", "paths": []}]
    with pytest.raises(ValidationFailure, match="no file paths"):
        validate_llm_steps(steps, snapshot)


def test_path_validation_skipped_when_no_changed_files():
    """When the snapshot has no changed files we cannot validate — allow any path."""
    snapshot = make_snapshot()  # no staged/modified/untracked
    steps = [{"kind": "push", "title": "Push", "detail": "d", "remote": "origin", "branch": "main"}]
    result = validate_llm_steps(steps, snapshot)
    assert result[0].kind.value == "push"
