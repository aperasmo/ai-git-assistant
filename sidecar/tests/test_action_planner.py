from __future__ import annotations

import pytest

from app.errors import ValidationFailure
from app.intent.action_planner import LocalActionPlanner
from app.intent.local_matcher import LocalIntentMatcher
from app.schemas.repositories import ChangedPath, RepositorySnapshot


def make_snapshot(
    *,
    branch: str = "dev_1",
    upstream: str = "origin/dev_1",
    upstream_remote: str = "origin",
    remote_names: list[str] | None = None,
) -> RepositorySnapshot:
    return RepositorySnapshot(
        repository_id="repo-1",
        branch=branch,
        head_commit="0123456789abcdef",
        upstream_remote=upstream_remote,
        upstream_branch=upstream,
        staged_changes=[],
        modified_changes=[
            ChangedPath(
                path="backend/app/routes/login.py",
                index_status=" ",
                worktree_status="M",
                kind="modified",
            )
        ],
        untracked_paths=[
            ChangedPath(
                path="frontend/src/Login.tsx",
                index_status="?",
                worktree_status="?",
                kind="untracked",
            )
        ],
        conflicts=[],
        ahead=0,
        behind=0,
        remote_last_refreshed_at=None,
        write_blocked_reason=None,
        fingerprint="test-fingerprint",
        recent_commits=[],
        remote_names=remote_names if remote_names is not None else ["origin"],
    )


def make_snapshot_no_upstream(*, branch: str = "dev_1") -> RepositorySnapshot:
    """Snapshot for a fresh local branch with no tracking upstream."""
    return make_snapshot(
        branch=branch,
        upstream=None,
        upstream_remote=None,
        remote_names=["origin"],
    )


def test_question_mark_status_request_resolves_as_read_plan():
    planner = LocalActionPlanner(LocalIntentMatcher())

    plan = planner.plan("repo-1", "What changed?", make_snapshot())

    assert plan.matched is True
    assert plan.plan_kind == "read"
    assert plan.requires_confirmation is False
    assert plan.read_action == "status"


def test_commit_selected_paths_then_push_creates_reviewable_plan():
    planner = LocalActionPlanner(LocalIntentMatcher())

    plan = planner.plan(
        "repo-1",
        'Commit backend/app/routes/login.py and frontend/src/Login.tsx with message "Add login validation", then push to dev_1',
        make_snapshot(),
    )

    assert plan.matched is True
    assert plan.plan_kind == "write"
    assert plan.requires_confirmation is True
    assert [step.kind for step in plan.steps] == ["stage", "commit", "push"]
    assert plan.steps[0].paths == [
        "backend/app/routes/login.py",
        "frontend/src/Login.tsx",
    ]
    assert plan.steps[1].commit_message == "Add login validation"
    assert plan.steps[2].remote == "origin"
    assert plan.steps[2].branch == "dev_1"


def test_push_to_a_different_branch_is_rejected_without_a_branch_switch():
    planner = LocalActionPlanner(LocalIntentMatcher())

    with pytest.raises(ValidationFailure, match="will not silently push"):
        planner.plan("repo-1", "push to main", make_snapshot())


def test_explicit_commit_rejects_unrelated_pre_staged_files():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(
        update={
            "staged_changes": [
                ChangedPath(
                    path="docs/unrelated.md",
                    index_status="M",
                    worktree_status=" ",
                    kind="staged",
                )
            ]
        }
    )

    with pytest.raises(ValidationFailure, match="already staged files outside"):
        planner.plan(
            "repo-1",
            'commit backend/app/routes/login.py with message "Add login validation"',
            snapshot,
        )


def test_commit_all_modified_files_stages_all_changed():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot()

    for phrase in [
        'commit my changes with message "Fix layout"',
        'commit all modified files with message "Fix layout"',
        'commit everything with message "Fix layout"',
        'commit changes with message "Fix layout"',
    ]:
        plan = planner.plan("repo-1", phrase, snapshot)
        assert plan.matched is True
        assert plan.plan_kind == "write"
        assert plan.requires_confirmation is True
        kinds = [s.kind.value for s in plan.steps]
        assert kinds == ["stage", "commit"], f"Failed for phrase: {phrase!r}"
        stage_step = plan.steps[0]
        staged_paths = set(stage_step.paths)
        assert "backend/app/routes/login.py" in staged_paths
        assert "frontend/src/Login.tsx" in staged_paths


def test_commit_all_modified_then_push():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot()

    plan = planner.plan(
        "repo-1",
        'commit my changes with message "Fix layout", then push',
        snapshot,
    )

    assert [s.kind.value for s in plan.steps] == ["stage", "commit", "push"]
    assert set(plan.steps[0].paths) == {
        "backend/app/routes/login.py",
        "frontend/src/Login.tsx",
    }


def test_commit_all_modified_raises_when_nothing_changed():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(
        update={"modified_changes": [], "untracked_paths": []}
    )

    with pytest.raises(ValidationFailure, match="no modified or untracked files"):
        planner.plan("repo-1", 'commit my changes with message "Oops"', snapshot)


def test_short_filename_resolves_to_full_path():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot()

    plan = planner.plan(
        "repo-1",
        'commit login.py with message "Fix login"',
        snapshot,
    )

    assert plan.matched is True
    assert plan.steps[0].paths == ["backend/app/routes/login.py"]


def test_push_with_no_upstream_uses_set_upstream_flag():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot_no_upstream()

    plan = planner.plan("repo-1", "push", snapshot)

    assert plan.matched is True
    assert plan.plan_kind == "write"
    assert plan.requires_confirmation is True
    push_step = plan.steps[0]
    assert push_step.kind.value == "push"
    assert push_step.set_upstream is True
    assert push_step.remote == "origin"
    assert push_step.branch == "dev_1"
    assert "--set-upstream" in (push_step.command_preview or "")


def test_commit_then_push_with_no_upstream_uses_set_upstream_flag():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot_no_upstream()

    plan = planner.plan(
        "repo-1",
        'Commit backend/app/routes/login.py with message "Fix login", then push to dev_1',
        snapshot,
    )

    assert [s.kind.value for s in plan.steps] == ["stage", "commit", "push"]
    push_step = plan.steps[2]
    assert push_step.set_upstream is True
    assert push_step.remote == "origin"
    assert push_step.branch == "dev_1"


# ---------------------------------------------------------------------------
# Pull
# ---------------------------------------------------------------------------

def test_pull_when_behind_creates_write_plan():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(update={"behind": 2})

    for phrase in ["pull", "git pull", "sync with remote"]:
        plan = planner.plan("repo-1", phrase, snapshot)
        assert plan.plan_kind == "write"
        assert plan.requires_confirmation is True
        step = plan.steps[0]
        assert step.kind.value == "pull"
        assert step.behind == 2
        assert "--ff-only" in (step.command_preview or "")


def test_pull_when_up_to_date_returns_info():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(update={"behind": 0})

    plan = planner.plan("repo-1", "pull", snapshot)
    assert plan.plan_kind == "info"
    assert plan.requires_confirmation is False


def test_pull_with_no_upstream_returns_info():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot_no_upstream()

    plan = planner.plan("repo-1", "pull", snapshot)
    assert plan.plan_kind == "info"
    assert "no upstream" in plan.steps[0].title.lower()


def test_pull_diverged_raises_error():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(update={"ahead": 1, "behind": 2})

    with pytest.raises(ValidationFailure, match="diverged"):
        planner.plan("repo-1", "pull", snapshot)


# ---------------------------------------------------------------------------
# Unstage
# ---------------------------------------------------------------------------

def test_unstage_staged_file_creates_plan():
    from app.schemas.repositories import ChangedPath
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(
        update={
            "staged_changes": [
                ChangedPath(path="backend/app/routes/login.py", index_status="M", worktree_status=" ", kind="staged")
            ]
        }
    )

    plan = planner.plan("repo-1", "unstage backend/app/routes/login.py", snapshot)
    assert plan.plan_kind == "write"
    step = plan.steps[0]
    assert step.kind.value == "unstage"
    assert "backend/app/routes/login.py" in step.paths
    assert "--staged" in (step.command_preview or "")


def test_unstage_when_nothing_staged_raises_error():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(update={"staged_changes": []})

    with pytest.raises(ValidationFailure, match="no staged files"):
        planner.plan("repo-1", "unstage login.py", snapshot)


# ---------------------------------------------------------------------------
# Discard
# ---------------------------------------------------------------------------

def test_discard_modified_file_creates_destructive_plan():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot()

    for phrase in [
        "discard backend/app/routes/login.py",
        "discard changes in backend/app/routes/login.py",
        "discard change in login.py",
    ]:
        plan = planner.plan("repo-1", phrase, snapshot)
        assert plan.plan_kind == "write"
        step = plan.steps[0]
        assert step.kind.value == "discard"
        assert "DESTRUCTIVE" in step.detail
        assert "backend/app/routes/login.py" in step.paths


def test_discard_when_nothing_modified_raises_error():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(update={"modified_changes": []})

    with pytest.raises(ValidationFailure, match="no modified files"):
        planner.plan("repo-1", "discard login.py", snapshot)


# ---------------------------------------------------------------------------
# Switch branch
# ---------------------------------------------------------------------------

def test_switch_branch_creates_plan():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(update={"staged_changes": [], "modified_changes": []})

    for phrase in ["switch to main", "checkout main"]:
        plan = planner.plan("repo-1", phrase, snapshot)
        assert plan.plan_kind == "write"
        step = plan.steps[0]
        assert step.kind.value == "switch"
        assert step.branch == "main"


def test_switch_when_uncommitted_changes_raises_error():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot()  # has modified_changes

    with pytest.raises(ValidationFailure, match="uncommitted changes"):
        planner.plan("repo-1", "switch to main", snapshot)


def test_switch_to_current_branch_returns_info():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(update={"staged_changes": [], "modified_changes": []})

    plan = planner.plan("repo-1", "switch to dev_1", snapshot)
    assert plan.plan_kind == "info"
    assert plan.requires_confirmation is False


# ---------------------------------------------------------------------------
# Create branch
# ---------------------------------------------------------------------------

def test_create_branch_creates_plan():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot()

    for phrase in ["create branch feature/login", "new branch feature/login"]:
        plan = planner.plan("repo-1", phrase, snapshot)
        assert plan.plan_kind == "write"
        step = plan.steps[0]
        assert step.kind.value == "create_branch"
        assert step.branch == "feature/login"
        assert "-c" in (step.command_preview or "")


# ---------------------------------------------------------------------------
# Stash
# ---------------------------------------------------------------------------

def test_stash_creates_plan():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot()

    for phrase in ["stash", "stash my changes", "stash changes"]:
        plan = planner.plan("repo-1", phrase, snapshot)
        assert plan.plan_kind == "write"
        step = plan.steps[0]
        assert step.kind.value == "stash"
        assert step.commit_message is None


def test_stash_with_message_includes_label():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot()

    plan = planner.plan("repo-1", 'stash with message "WIP login form"', snapshot)
    assert plan.plan_kind == "write"
    step = plan.steps[0]
    assert step.commit_message == "WIP login form"
    assert "WIP login form" in (step.command_preview or "")


def test_stash_when_nothing_to_stash_raises_error():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(update={"staged_changes": [], "modified_changes": []})

    with pytest.raises(ValidationFailure, match="no local changes"):
        planner.plan("repo-1", "stash", snapshot)


# ---------------------------------------------------------------------------
# Stash pop
# ---------------------------------------------------------------------------

def test_stash_pop_creates_plan():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot().model_copy(update={"staged_changes": [], "modified_changes": []})

    for phrase in ["stash pop", "restore stash", "apply stash"]:
        plan = planner.plan("repo-1", phrase, snapshot)
        assert plan.plan_kind == "write"
        step = plan.steps[0]
        assert step.kind.value == "stash_pop"
        assert "stash pop" in (step.command_preview or "")


# ---------------------------------------------------------------------------
# Delete branch
# ---------------------------------------------------------------------------

def test_delete_branch_creates_plan():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot()

    for phrase in ["delete branch old-feature", "remove branch old-feature"]:
        plan = planner.plan("repo-1", phrase, snapshot)
        assert plan.plan_kind == "write"
        step = plan.steps[0]
        assert step.kind.value == "delete_branch"
        assert step.branch == "old-feature"
        assert "-d" in (step.command_preview or "")


def test_delete_current_branch_raises_error():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot()  # branch="dev_1"

    with pytest.raises(ValidationFailure, match="currently checked-out"):
        planner.plan("repo-1", "delete branch dev_1", snapshot)


def test_push_with_no_remote_raises_clear_error():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot_no_upstream().model_copy(update={"remote_names": []})

    with pytest.raises(ValidationFailure, match="no Git remote"):
        planner.plan("repo-1", "push", snapshot)


def test_push_with_multiple_remotes_and_no_origin_requires_explicit_remote():
    planner = LocalActionPlanner(LocalIntentMatcher())
    snapshot = make_snapshot_no_upstream().model_copy(
        update={"remote_names": ["upstream", "fork"]}
    )

    with pytest.raises(ValidationFailure, match="Multiple remotes"):
        planner.plan("repo-1", "push", snapshot)
