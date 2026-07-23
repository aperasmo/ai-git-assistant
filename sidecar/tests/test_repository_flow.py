from __future__ import annotations

from pathlib import Path

from app.git.client import GitClient, GitResult
from app.llm.router import CommitMessageDraft
from app.schemas.repositories import ActionPlanStep, PlanStepKind


def test_git_error_prefers_actionable_failure_line():
    error = GitClient._safe_error(
        GitResult(
            stdout="",
            stderr=(
                "From https://github.com/example/repo\n"
                " * branch            main       -> FETCH_HEAD\n"
                "fatal: Not possible to fast-forward, aborting.\n"
            ),
            return_code=128,
        )
    )

    assert error == "fatal: Not possible to fast-forward, aborting."


def test_register_and_read_status(app_client, auth_headers, git_repository):
    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200
    repository = register.json()
    assert repository["displayName"] == "demo-repository"

    snapshot = app_client.get(
        f"/v1/repositories/{repository['id']}/snapshot",
        headers=auth_headers,
    )
    assert snapshot.status_code == 200
    assert snapshot.json()["modifiedChanges"]

    status = app_client.post(
        f"/v1/repositories/{repository['id']}/read-actions",
        headers=auth_headers,
        json={"action": "status"},
    )
    assert status.status_code == 200
    assert status.json()["title"] == "Git Status"
    assert "Changes not staged for commit:" in status.json()["content"]
    assert "modified:\tREADME.md" in status.json()["content"]


def test_add_to_gitignore_appends_exact_untracked_paths(app_client, auth_headers, git_repository):
    (git_repository / "ai-git-assistant.db").write_text("runtime\n", encoding="utf-8")
    (git_repository / "ai-git-assistant.db-shm").write_text("runtime\n", encoding="utf-8")

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/add-to-gitignore",
        headers=auth_headers,
        json={
            "paths": [
                "ai-git-assistant.db",
                "ai-git-assistant.db-shm",
                "ai-git-assistant.db",
            ],
        },
    )

    assert response.status_code == 200, response.json()
    assert response.json()["ok"] is True
    gitignore = (git_repository / ".gitignore").read_text(encoding="utf-8")
    assert "# -- AI GIT ASSISTANT --" in gitignore
    assert gitignore.count("ai-git-assistant.db\n") == 1
    assert gitignore.count("ai-git-assistant.db-shm\n") == 1

    snapshot = app_client.get(
        f"/v1/repositories/{repository_id}/snapshot",
        headers=auth_headers,
    )
    assert snapshot.status_code == 200, snapshot.json()
    untracked_paths = {item["path"] for item in snapshot.json()["untrackedPaths"]}
    assert "ai-git-assistant.db" not in untracked_paths
    assert "ai-git-assistant.db-shm" not in untracked_paths
    assert ".gitignore" in untracked_paths


def test_local_matcher(app_client, auth_headers, git_repository):
    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "last 5 commits"},
    )

    assert response.status_code == 200, response.json()

    body = response.json()
    assert body["matched"] is True
    assert body["planKind"] == "read"
    assert body["requiresConfirmation"] is False
    assert body["readAction"] == "log"
    assert body["readParams"]["limit"] == 5
    assert body["steps"][0]["kind"] == "read"


def test_git_logs_last_count_resolves_as_read_plan(app_client, auth_headers, git_repository):
    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "git logs last 5"},
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["matched"] is True
    assert body["planKind"] == "read"
    assert body["requiresConfirmation"] is False
    assert body["readAction"] == "log"
    assert body["readParams"]["limit"] == 5
    assert body["source"] == "local"


def test_review_status_resolves_as_read_plan(app_client, auth_headers, git_repository):
    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "review status"},
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["matched"] is True
    assert body["planKind"] == "read"
    assert body["requiresConfirmation"] is False
    assert body["readAction"] == "review_status"
    assert body["source"] == "local"


def test_read_shaped_unmatched_request_does_not_use_ai_write_fallback(
    app_client,
    auth_headers,
    git_repository,
):
    class FakeLLMRouter:
        def __init__(self):
            self.calls = 0

        def plan(self, message, snapshot):
            self.calls += 1
            return [
                ActionPlanStep(
                    kind=PlanStepKind.STAGE,
                    title="Stage all files",
                    detail="Should not be used for read-only text.",
                    paths=["README.md"],
                )
            ]

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    repository_id = register.json()["id"]
    app_client.app.state.repository_service.set_external_llm_allowed(repository_id, True)
    fake_router = FakeLLMRouter()
    app_client.app.state.repository_service._llm_router = fake_router

    response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "git history"},
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["matched"] is False
    assert body["planKind"] != "write"
    assert body["requiresConfirmation"] is False
    assert "read-only Git request" in body["explanation"]
    assert fake_router.calls == 0


def test_register_nested_folder_uses_repository_root(app_client, auth_headers, git_repository):
    nested_folder = git_repository / "backend"
    nested_folder.mkdir()

    response = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(nested_folder)},
    )

    assert response.status_code == 200, response.json()
    assert response.json()["displayName"] == "demo-repository"

def test_classify_plain_folder_requires_explicit_initialisation(
    app_client,
    auth_headers,
    tmp_path,
):
    selected_folder = tmp_path / "plain-folder"
    selected_folder.mkdir()

    response = app_client.post(
        "/v1/repositories/classify",
        headers=auth_headers,
        json={"path": str(selected_folder)},
    )

    assert response.status_code == 200, response.json()

    body = response.json()
    assert body["kind"] == "initialisation_required"
    assert body["selectedPath"] == str(selected_folder.resolve())
    assert body["repositoryRoot"] is None
    assert body["canInitialise"] is True


def test_classify_plain_folder_under_broken_parent_git_can_initialise(
    app_client,
    auth_headers,
    tmp_path,
):
    parent = tmp_path / "workspace"
    selected_folder = parent / "my-portfolio"
    selected_folder.mkdir(parents=True)
    (parent / ".git").mkdir()

    response = app_client.post(
        "/v1/repositories/classify",
        headers=auth_headers,
        json={"path": str(selected_folder)},
    )

    assert response.status_code == 200, response.json()

    body = response.json()
    assert body["kind"] == "initialisation_required"
    assert body["selectedPath"] == str(selected_folder.resolve())
    assert body["repositoryRoot"] is None
    assert body["canInitialise"] is True
    assert "Broken or incomplete Git metadata was found above this folder" in body["message"]


def test_classify_folder_with_own_broken_git_metadata_is_unsupported(
    app_client,
    auth_headers,
    tmp_path,
):
    selected_folder = tmp_path / "broken-repository"
    selected_folder.mkdir()
    (selected_folder / ".git").mkdir()

    response = app_client.post(
        "/v1/repositories/classify",
        headers=auth_headers,
        json={"path": str(selected_folder)},
    )

    assert response.status_code == 200, response.json()

    body = response.json()
    assert body["kind"] == "unsupported_repository"
    assert body["canInitialise"] is False
    assert "Git metadata was found" in body["message"]


def test_classify_existing_repository(app_client, auth_headers, git_repository):
    response = app_client.post(
        "/v1/repositories/classify",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )

    assert response.status_code == 200, response.json()

    body = response.json()
    assert body["kind"] == "existing_repository"
    assert body["selectedPath"] == str(git_repository.resolve())
    assert body["repositoryRoot"] == str(git_repository.resolve())
    assert body["canInitialise"] is False


def test_classify_nested_folder_returns_parent_repository_root(
    app_client,
    auth_headers,
    git_repository,
):
    nested_folder = git_repository / "backend"
    nested_folder.mkdir()

    response = app_client.post(
        "/v1/repositories/classify",
        headers=auth_headers,
        json={"path": str(nested_folder)},
    )

    assert response.status_code == 200, response.json()

    body = response.json()
    assert body["kind"] == "nested_repository"
    assert body["selectedPath"] == str(nested_folder.resolve())
    assert body["repositoryRoot"] == str(git_repository.resolve())
    assert body["canInitialise"] is False

def test_initialise_and_register_plain_folder_after_confirmation(
    app_client,
    auth_headers,
    tmp_path,
):
    selected_folder = tmp_path / "new-repository"
    selected_folder.mkdir()

    response = app_client.post(
        "/v1/repositories/initialise-and-register",
        headers=auth_headers,
        json={
            "path": str(selected_folder),
            "confirmed": True,
        },
    )

    assert response.status_code == 200, response.json()
    assert (selected_folder / ".git").is_dir()
    assert (
        (selected_folder / ".git" / "HEAD")
        .read_text(encoding="utf-8")
        .strip()
        == "ref: refs/heads/main"
    )    

def test_initialise_and_register_rejects_unconfirmed_request(
    app_client,
    auth_headers,
    tmp_path,
):
    selected_folder = tmp_path / "unconfirmed-repository"
    selected_folder.mkdir()

    response = app_client.post(
        "/v1/repositories/initialise-and-register",
        headers=auth_headers,
        json={
            "path": str(selected_folder),
            "confirmed": False,
        },
    )

    assert response.status_code == 422, response.json()
    assert not (selected_folder / ".git").exists()

def test_initialise_and_register_rejects_existing_repository(
    app_client,
    auth_headers,
    git_repository,
):
    response = app_client.post(
        "/v1/repositories/initialise-and-register",
        headers=auth_headers,
        json={
            "path": str(git_repository),
            "confirmed": True,
        },
    )

    assert response.status_code == 422, response.json()
    assert response.json()["code"] == "validation_failure"
    assert (git_repository / ".git").is_dir()    


def test_initialise_and_register_rejects_nested_folder(
    app_client,
    auth_headers,
    git_repository,
):
    nested_folder = git_repository / "backend"
    nested_folder.mkdir()

    response = app_client.post(
        "/v1/repositories/initialise-and-register",
        headers=auth_headers,
        json={
            "path": str(nested_folder),
            "confirmed": True,
        },
    )

    assert response.status_code == 422, response.json()
    assert response.json()["code"] == "validation_failure"
    assert (git_repository / ".git").is_dir()
    assert not (nested_folder / ".git").exists()

def test_read_action_lists_current_local_branch(
    app_client,
    auth_headers,
    git_repository,
):
    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )

    assert register.status_code == 200, register.json()

    repository_id = register.json()["id"]
    response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={
            "action": "branches",
            "params": {},
        },
    )

    assert response.status_code == 200, response.json()
    branches = response.json()["content"].splitlines()

    assert branches
    assert branches != ["No local branches found."]
    assert any(branch.startswith("* ") for branch in branches)


def test_phase_c_read_actions_return_rich_git_context(
    app_client,
    auth_headers,
    git_repository,
):
    import subprocess

    subprocess.run(
        ["git", "stash", "push", "-m", "phase-c-stash"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    (git_repository / "README.md").write_text("# Demo\n\nChanged again.\n", encoding="utf-8")

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    diff_response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "diff", "params": {"scope": "all"}},
    )
    assert diff_response.status_code == 200, diff_response.json()
    assert diff_response.json()["title"] == "Patch Diff"
    assert diff_response.json()["contentKind"] == "diff"
    assert "diff --git" in diff_response.json()["content"]

    graph_response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "graph"},
    )
    assert graph_response.status_code == 200, graph_response.json()
    assert graph_response.json()["contentKind"] == "graph"
    assert "Initial commit" in graph_response.json()["content"]

    stash_list_response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "stashes"},
    )
    assert stash_list_response.status_code == 200, stash_list_response.json()
    assert "stash@{0}" in stash_list_response.json()["content"]
    assert "phase-c-stash" in stash_list_response.json()["content"]

    stash_show_response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "stash_show", "params": {"stash_ref": "stash@{0}"}},
    )
    assert stash_show_response.status_code == 200, stash_show_response.json()
    assert stash_show_response.json()["contentKind"] == "diff"
    assert "README.md" in stash_show_response.json()["content"]


def test_phase_c_remote_read_action_lists_origin(
    app_client,
    auth_headers,
    git_repository_with_remote,
):
    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository_with_remote)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "remotes"},
    )

    assert response.status_code == 200, response.json()
    assert response.json()["title"] == "Remotes"
    assert "origin" in response.json()["content"]


def test_snapshot_detects_remote_providers(
    app_client,
    auth_headers,
    git_repository,
):
    import subprocess

    subprocess.run(
        ["git", "remote", "add", "origin", "https://gitlab.com/example/demo-repository.git"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "remote", "add", "mirror", "git@github.com:example/demo-repository.git"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    snapshot = app_client.get(
        f"/v1/repositories/{repository_id}/snapshot",
        headers=auth_headers,
    )

    assert snapshot.status_code == 200, snapshot.json()
    providers = {item["remote"]: item for item in snapshot.json()["remoteProviders"]}
    assert providers["mirror"] == {
        "remote": "mirror",
        "provider": "github",
        "label": "GitHub",
        "host": "github.com",
        "url": "git@github.com:example/demo-repository.git",
    }
    assert providers["origin"] == {
        "remote": "origin",
        "provider": "gitlab",
        "label": "GitLab",
        "host": "gitlab.com",
        "url": "https://gitlab.com/example/demo-repository.git",
    }


def test_phase_c_file_history_and_blame_read_actions(
    app_client,
    auth_headers,
    git_repository,
):
    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    history_response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "file_history", "params": {"path": "README.md"}},
    )
    assert history_response.status_code == 200, history_response.json()
    assert history_response.json()["title"] == "History: README.md"
    assert "Initial commit" in history_response.json()["content"]

    blame_response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "blame", "params": {"path": "README.md"}},
    )
    assert blame_response.status_code == 200, blame_response.json()
    assert blame_response.json()["title"] == "Blame: README.md"
    assert "Test User" in blame_response.json()["content"]


def test_phase_c_tag_read_create_push_and_delete_flow(
    app_client,
    auth_headers,
    git_repository_with_remote,
):
    import subprocess

    repo = git_repository_with_remote

    subprocess.run(
        ["git", "add", "login.py"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "bootstrap release"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    create_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": 'create tag v0.3.0 with message "Release v0.3.0"'},
    )
    assert create_plan_response.status_code == 200, create_plan_response.json()
    create_plan = create_plan_response.json()
    assert create_plan["steps"][0]["kind"] == "create_tag"
    assert create_plan["steps"][0]["tagName"] == "v0.3.0"

    create_response = app_client.post(
        f"/v1/repositories/{repository_id}/execute-plan",
        headers=auth_headers,
        json={"planId": create_plan["planId"]},
    )
    assert create_response.status_code == 200, create_response.json()
    assert create_response.json()["title"] == "Tag 'v0.3.0' created"

    tags_response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "tags"},
    )
    assert tags_response.status_code == 200, tags_response.json()
    assert "v0.3.0" in tags_response.json()["content"]

    tag_show_response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "tag_show", "params": {"tag_name": "v0.3.0"}},
    )
    assert tag_show_response.status_code == 200, tag_show_response.json()
    assert tag_show_response.json()["title"] == "Tag: v0.3.0"
    assert "Release v0.3.0" in tag_show_response.json()["content"]

    push_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "push tag v0.3.0"},
    )
    assert push_plan_response.status_code == 200, push_plan_response.json()
    push_plan = push_plan_response.json()
    assert push_plan["steps"][0]["kind"] == "push_tag"
    assert push_plan["steps"][0]["remote"] == "origin"

    push_response = app_client.post(
        f"/v1/repositories/{repository_id}/execute-plan",
        headers=auth_headers,
        json={"planId": push_plan["planId"]},
    )
    assert push_response.status_code == 200, push_response.json()
    assert push_response.json()["title"] == "Tag 'v0.3.0' pushed"

    remote_tags = subprocess.run(
        ["git", "ls-remote", "--tags", "origin", "v0.3.0"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "refs/tags/v0.3.0" in remote_tags

    delete_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "delete tag v0.3.0"},
    )
    assert delete_plan_response.status_code == 200, delete_plan_response.json()
    delete_plan = delete_plan_response.json()
    assert delete_plan["steps"][0]["kind"] == "delete_tag"

    delete_response = app_client.post(
        f"/v1/repositories/{repository_id}/execute-plan",
        headers=auth_headers,
        json={"planId": delete_plan["planId"]},
    )
    assert delete_response.status_code == 200, delete_response.json()
    assert delete_response.json()["title"] == "Tag 'v0.3.0' deleted"
    assert subprocess.run(
        ["git", "tag", "--list", "v0.3.0"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip() == ""


def test_generate_commit_message_requires_repository_ai_opt_in(
    app_client,
    auth_headers,
    git_repository,
):
    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/generate-commit-message",
        headers=auth_headers,
        json={"paths": ["README.md"]},
    )

    assert response.status_code == 422, response.json()
    assert "disabled" in response.json()["detail"]


def test_generate_commit_message_uses_selected_changed_files(
    app_client,
    auth_headers,
    git_repository,
):
    template_path = Path(__file__).resolve().parents[2] / "docs" / "TEAM_CONTEXT_TEMPLATE.md"
    team_context_dir = git_repository / ".ai-git-assistant"
    team_context_dir.mkdir()
    (team_context_dir / "team-context.md").write_text(
        template_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    class FakeLLMRouter:
        def __init__(self) -> None:
            self.diff_context = ""
            self.style = ""

        def commit_message(self, *, branch, diff_context, style="detailed"):
            self.diff_context = diff_context
            self.style = style
            return CommitMessageDraft(
                subject="Update README copy",
                body=["Refresh README documentation"],
                confidence="high",
                detected_scope=["docs"],
                alternatives=["Refresh README content"],
            )

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]
    snapshot_response = app_client.get(
        f"/v1/repositories/{repository_id}/snapshot",
        headers=auth_headers,
    )
    assert snapshot_response.status_code == 200, snapshot_response.json()
    assert snapshot_response.json()["teamContext"]["available"] is True
    assert snapshot_response.json()["teamContext"]["path"] == ".ai-git-assistant/team-context.md"

    allow_response = app_client.post(
        f"/v1/repositories/{repository_id}/set-llm",
        headers=auth_headers,
        json={"allowed": True},
    )
    assert allow_response.status_code == 200, allow_response.json()

    fake_router = FakeLLMRouter()
    app_client.app.state.repository_service._llm_router = fake_router

    response = app_client.post(
        f"/v1/repositories/{repository_id}/generate-commit-message",
        headers=auth_headers,
        json={"paths": ["README.md"], "style": "conventional"},
    )

    assert response.status_code == 200, response.json()
    assert response.json()["subject"] == "Update README copy"
    assert response.json()["body"] == ["Refresh README documentation"]
    assert response.json()["style"] == "conventional"
    assert response.json()["confidence"] == "high"
    assert response.json()["detectedScope"] == ["docs"]
    assert response.json()["alternatives"] == ["Refresh README content"]
    assert response.json()["message"] == "Update README copy\n\n- Refresh README documentation"
    assert response.json()["contextSummary"] == "Generated one conventional message from 1 selected file."
    assert response.json()["privacyReceipt"]["externalProvider"] is True
    assert response.json()["privacyReceipt"]["files"] == ["README.md"]
    assert "Organized change map" in response.json()["privacyReceipt"]["contextItems"]
    assert "Diff stats" in response.json()["privacyReceipt"]["contextItems"]
    assert "Repository team context" in response.json()["privacyReceipt"]["contextItems"]
    assert "Recent commit subjects" in response.json()["privacyReceipt"]["contextItems"]
    assert "Tracked file patch" in response.json()["privacyReceipt"]["contextItems"]
    assert fake_router.style == "conventional"
    assert "Group: README.md" in fake_router.diff_context
    assert "Repository team context (.ai-git-assistant/team-context.md):" in fake_router.diff_context
    assert "Use Conventional Commits" in fake_router.diff_context
    assert "Include a Validation section" in fake_router.diff_context
    assert "+2/-0" in fake_router.diff_context
    assert "Recent commit style examples:" in fake_router.diff_context
    assert "README.md" in fake_router.diff_context
    assert "Changed." in fake_router.diff_context


def test_create_team_context_template_adds_repo_guidance_file(
    app_client,
    auth_headers,
    git_repository,
):
    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    context_path = git_repository / ".ai-git-assistant" / "team-context.md"
    assert not context_path.exists()

    response = app_client.post(
        f"/v1/repositories/{repository_id}/team-context/template",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.json()
    assert response.json()["title"] == "Team context template added"
    assert response.json()["snapshot"]["teamContext"]["available"] is True
    assert response.json()["snapshot"]["teamContext"]["path"] == ".ai-git-assistant/team-context.md"
    assert context_path.exists()
    content = context_path.read_text(encoding="utf-8")
    assert "## Commit Message Style" in content
    assert "## Pull Request / Merge Request Style" in content
    assert "free of secrets" in content

    duplicate_response = app_client.post(
        f"/v1/repositories/{repository_id}/team-context/template",
        headers=auth_headers,
    )
    assert duplicate_response.status_code == 422, duplicate_response.json()
    assert "already exists" in duplicate_response.json()["detail"]


def test_generate_commit_message_allows_large_file_selection(
    app_client,
    auth_headers,
    git_repository,
):
    class FakeLLMRouter:
        def __init__(self) -> None:
            self.diff_context = ""

        def commit_message(self, *, branch, diff_context, style="detailed"):
            self.diff_context = diff_context
            return CommitMessageDraft(
                subject="Update generated files",
                body=["Refresh generated text artifacts"],
            )

    paths: list[str] = []
    for index in range(43):
        path = f"generated/file-{index:02d}.txt"
        file_path = git_repository / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"Generated {index}\n", encoding="utf-8")
        paths.append(path)

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    allow_response = app_client.post(
        f"/v1/repositories/{repository_id}/set-llm",
        headers=auth_headers,
        json={"allowed": True},
    )
    assert allow_response.status_code == 200, allow_response.json()

    fake_router = FakeLLMRouter()
    app_client.app.state.repository_service._llm_router = fake_router

    response = app_client.post(
        f"/v1/repositories/{repository_id}/generate-commit-message",
        headers=auth_headers,
        json={"paths": paths},
    )

    assert response.status_code == 200, response.json()
    assert response.json()["message"] == "Update generated files\n\n- Refresh generated text artifacts"
    assert response.json()["contextSummary"] == "Generated one detailed message from 43 selected files."
    assert "Organized change map" in fake_router.diff_context
    assert "Group: generated" in fake_router.diff_context
    assert response.json()["privacyReceipt"]["files"] == paths


def test_generate_change_summary_returns_pr_and_commit_suggestions(
    app_client,
    auth_headers,
    git_repository,
):
    from app.schemas.repositories import CommitSuggestion, GenerateChangeSummaryResponse

    class FakeLLMRouter:
        def __init__(self) -> None:
            self.diff_context = ""

        def change_summary(self, *, branch, diff_context, context_summary):
            self.diff_context = diff_context
            return GenerateChangeSummaryResponse(
                branch_summary="README copy was refreshed.",
                file_summaries=["README.md: updated project copy"],
                pr_title="Refresh README copy",
                pr_body="Summary:\n- Updates README copy",
                commit_suggestions=[
                    CommitSuggestion(
                        message="Refresh README copy",
                        files=["README.md"],
                        rationale="Documentation-only change.",
                    )
                ],
                context_summary=context_summary,
            )

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    allow_response = app_client.post(
        f"/v1/repositories/{repository_id}/set-llm",
        headers=auth_headers,
        json={"allowed": True},
    )
    assert allow_response.status_code == 200, allow_response.json()

    fake_router = FakeLLMRouter()
    app_client.app.state.repository_service._llm_router = fake_router

    response = app_client.post(
        f"/v1/repositories/{repository_id}/generate-change-summary",
        headers=auth_headers,
        json={"paths": ["README.md"]},
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["branchSummary"] == "README copy was refreshed."
    assert body["prTitle"] == "Refresh README copy"
    assert body["commitSuggestions"][0]["message"] == "Refresh README copy"
    assert body["privacyReceipt"]["purpose"] == "Analyze changes and suggest commits"
    assert "README.md" in fake_router.diff_context


def test_draft_github_release_uses_configured_token_and_uploads_asset(
    app_client,
    auth_headers,
    git_repository,
    tmp_path,
):
    import subprocess

    from app.schemas.settings import UpdateGitHubSettingsRequest
    from app.services.github_release_service import GitHubDraftReleaseResult

    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/example/demo-repository.git"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )

    app_client.app.state.settings_service.update_github_settings(
        UpdateGitHubSettingsRequest(token="github-token")
    )
    asset = tmp_path / "AI Git Assistant_0.4.0_x64-setup.exe"
    asset.write_bytes(b"installer")

    calls: list[dict] = []

    class FakeGitHubReleaseClient:
        def __init__(self, token: str) -> None:
            self.token = token

        def create_draft_release(self, **kwargs):
            calls.append({"token": self.token, **kwargs})
            return GitHubDraftReleaseResult(
                tag_name=kwargs["tag_name"],
                release_url="https://github.com/example/demo-repository/releases/tag/v0.4.0",
                asset_url="https://github.com/example/demo-repository/releases/download/v0.4.0/asset.exe",
                asset_name=kwargs["asset_path"].name,
                asset_sha256="fake-sha",
            )

    app_client.app.state.repository_service._github_release_client_factory = FakeGitHubReleaseClient

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/github/releases/draft",
        headers=auth_headers,
        json={
            "tagName": "v0.4.0",
            "title": "v0.4.0 - Phase D",
            "body": "Release notes",
            "assetPath": str(asset),
            "prerelease": False,
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["repository"] == "example/demo-repository"
    assert body["releaseUrl"].endswith("/releases/tag/v0.4.0")
    assert body["assetName"] == asset.name
    assert calls[0]["token"] == "github-token"
    assert calls[0]["repository"].slug == "example/demo-repository"
    assert calls[0]["tag_name"] == "v0.4.0"
    assert calls[0]["title"] == "v0.4.0 - Phase D"
    assert calls[0]["asset_path"] == asset


def test_draft_github_release_uploads_multiple_assets(
    app_client,
    auth_headers,
    git_repository,
    tmp_path,
):
    import subprocess

    from app.schemas.settings import UpdateGitHubSettingsRequest
    from app.services.github_release_service import GitHubDraftReleaseResult, GitHubReleaseAssetResult

    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/example/demo-repository.git"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )

    app_client.app.state.settings_service.update_github_settings(
        UpdateGitHubSettingsRequest(token="github-token")
    )
    windows_asset = tmp_path / "AI Git Assistant_0.7.6_x64-setup.exe"
    linux_asset = tmp_path / "AI Git Assistant_0.7.6_amd64.deb"
    windows_asset.write_bytes(b"windows-installer")
    linux_asset.write_bytes(b"linux-installer")

    calls: list[dict] = []

    class FakeGitHubReleaseClient:
        def __init__(self, token: str) -> None:
            self.token = token

        def create_draft_release(self, **kwargs):
            calls.append({"token": self.token, **kwargs})
            assets = tuple(
                GitHubReleaseAssetResult(
                    name=asset_path.name,
                    url=f"https://github.com/example/demo-repository/releases/download/v0.7.6/{asset_path.name}",
                    sha256=f"sha-{index}",
                )
                for index, asset_path in enumerate(kwargs["asset_paths"], start=1)
            )
            return GitHubDraftReleaseResult(
                tag_name=kwargs["tag_name"],
                release_url="https://github.com/example/demo-repository/releases/tag/v0.7.6",
                asset_url=assets[0].url,
                asset_name=assets[0].name,
                asset_sha256=assets[0].sha256,
                assets=assets,
            )

    app_client.app.state.repository_service._github_release_client_factory = FakeGitHubReleaseClient

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/github/releases/draft",
        headers=auth_headers,
        json={
            "tagName": "v0.7.6",
            "title": "Release v0.7.6 - Linux Preview",
            "body": "Release notes",
            "assetPaths": [str(windows_asset), str(linux_asset)],
            "prerelease": False,
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["repository"] == "example/demo-repository"
    assert [asset["name"] for asset in body["assets"]] == [windows_asset.name, linux_asset.name]
    assert body["assetName"] == windows_asset.name
    assert "Assets uploaded: 2" in body["content"]
    assert calls[0]["asset_path"] == windows_asset
    assert calls[0]["asset_paths"] == [windows_asset, linux_asset]


def test_draft_github_release_can_update_existing_draft(
    app_client,
    auth_headers,
    git_repository,
    tmp_path,
):
    import subprocess

    from app.schemas.settings import UpdateGitHubSettingsRequest
    from app.services.github_release_service import GitHubDraftReleaseResult, GitHubReleaseAssetResult

    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/example/demo-repository.git"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )

    app_client.app.state.settings_service.update_github_settings(
        UpdateGitHubSettingsRequest(token="github-token")
    )
    windows_asset = tmp_path / "AI Git Assistant_0.7.7_x64-setup.exe"
    linux_asset = tmp_path / "AI Git Assistant_0.7.7_amd64.deb"
    windows_asset.write_bytes(b"windows-installer")
    linux_asset.write_bytes(b"linux-installer")

    class FakeGitHubReleaseClient:
        def __init__(self, token: str) -> None:
            self.token = token

        def create_draft_release(self, **kwargs):
            return GitHubDraftReleaseResult(
                tag_name=kwargs["tag_name"],
                release_url="https://github.com/example/demo-repository/releases/tag/v0.7.7",
                asset_url="https://github.com/example/demo-repository/releases/download/v0.7.7/linux.deb",
                asset_name=linux_asset.name,
                asset_sha256="sha-linux",
                assets=(
                    GitHubReleaseAssetResult(
                        name=windows_asset.name,
                        url="https://github.com/example/demo-repository/releases/download/v0.7.7/windows.exe",
                        sha256="sha-windows",
                        status="already_exists",
                    ),
                    GitHubReleaseAssetResult(
                        name=linux_asset.name,
                        url="https://github.com/example/demo-repository/releases/download/v0.7.7/linux.deb",
                        sha256="sha-linux",
                        status="uploaded",
                    ),
                ),
                action="updated",
            )

    app_client.app.state.repository_service._github_release_client_factory = FakeGitHubReleaseClient

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/github/releases/draft",
        headers=auth_headers,
        json={
            "tagName": "v0.7.7",
            "title": "Release v0.7.7",
            "body": "Release notes",
            "assetPaths": [str(windows_asset), str(linux_asset)],
            "prerelease": False,
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["action"] == "updated"
    assert body["title"] == "GitHub Draft Release Updated"
    assert "A draft GitHub release was updated" in body["summary"]
    assert "1 asset(s) uploaded" in body["summary"]
    assert "1 asset(s) already existed" in body["summary"]
    assert [asset["status"] for asset in body["assets"]] == ["already_exists", "uploaded"]
    assert "Already on draft: 1" in body["content"]


def test_get_github_draft_release_returns_existing_details(
    app_client,
    auth_headers,
    git_repository,
):
    import subprocess

    from app.schemas.settings import UpdateGitHubSettingsRequest
    from app.services.github_release_service import GitHubDraftReleaseDetails, GitHubReleaseAssetResult

    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/example/demo-repository.git"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )

    app_client.app.state.settings_service.update_github_settings(
        UpdateGitHubSettingsRequest(token="github-token")
    )

    class FakeGitHubReleaseClient:
        def __init__(self, token: str) -> None:
            self.token = token

        def get_draft_release(self, **kwargs):
            return GitHubDraftReleaseDetails(
                tag_name=kwargs["tag_name"],
                title="Release v0.7.7",
                body="Existing release notes",
                release_url="https://github.com/example/demo-repository/releases/tag/v0.7.7",
                assets=(
                    GitHubReleaseAssetResult(
                        name="AI Git Assistant_0.7.7_x64-setup.exe",
                        url="https://github.com/example/demo-repository/releases/download/v0.7.7/windows.exe",
                        sha256=None,
                        status="existing",
                    ),
                ),
            )

    app_client.app.state.repository_service._github_release_client_factory = FakeGitHubReleaseClient

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/github/releases/draft/details",
        headers=auth_headers,
        json={"tagName": "v0.7.7"},
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["repository"] == "example/demo-repository"
    assert body["tagName"] == "v0.7.7"
    assert body["title"] == "Release v0.7.7"
    assert body["body"] == "Existing release notes"
    assert body["assets"][0]["name"] == "AI Git Assistant_0.7.7_x64-setup.exe"
    assert body["assets"][0]["status"] == "existing"


def test_github_draft_release_details_reads_assets_url():
    import httpx

    from app.services.github_release_service import GitHubReleaseClient, GitHubRepositoryRef

    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if str(request.url).endswith("/releases/tags/v0.7.7"):
            return httpx.Response(
                200,
                json={
                    "id": 10,
                    "tag_name": "v0.7.7",
                    "name": "Release v0.7.7",
                    "body": "Release notes",
                    "draft": True,
                    "html_url": "https://github.com/example/demo-repository/releases/tag/v0.7.7",
                    "assets_url": "https://api.github.com/repos/example/demo-repository/releases/10/assets",
                    "assets": [
                        {
                            "name": "AI Git Assistant_0.7.7_x64-setup.exe",
                            "browser_download_url": "embedded-only",
                        }
                    ],
                },
                request=request,
            )
        if str(request.url).startswith("https://api.github.com/repos/example/demo-repository/releases/10/assets"):
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "AI Git Assistant_0.7.7_x64-setup.exe",
                        "browser_download_url": "https://github.com/example/demo-repository/releases/download/v0.7.7/windows.exe",
                    },
                    {
                        "name": "AI Git Assistant_0.7.7_amd64.deb",
                        "browser_download_url": "https://github.com/example/demo-repository/releases/download/v0.7.7/linux.deb",
                    },
                ],
                request=request,
            )
        return httpx.Response(404, json={"message": "not found"}, request=request)

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    httpx.Client = fake_client
    try:
        details = GitHubReleaseClient("token").get_draft_release(
            repository=GitHubRepositoryRef(owner="example", repo="demo-repository"),
            tag_name="v0.7.7",
        )
    finally:
        httpx.Client = original_client

    assert [asset.name for asset in details.assets] == [
        "AI Git Assistant_0.7.7_x64-setup.exe",
        "AI Git Assistant_0.7.7_amd64.deb",
    ]
    assert any("/releases/10/assets" in url for url in requests)


def test_github_draft_release_creates_missing_tag_ref_before_draft():
    import json

    import httpx

    from app.services.github_release_service import GitHubReleaseClient, GitHubRepositoryRef

    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path.endswith("/releases/tags/v0.7.7"):
            return httpx.Response(404, json={"message": "not found"}, request=request)
        if request.method == "GET" and request.url.path.endswith("/releases"):
            return httpx.Response(200, json=[], request=request)
        if request.method == "GET" and request.url.path.endswith("/git/ref/tags/v0.7.7"):
            return httpx.Response(404, json={"message": "not found"}, request=request)
        if request.method == "POST" and request.url.path.endswith("/git/refs"):
            assert json.loads(request.content.decode("utf-8")) == {
                "ref": "refs/tags/v0.7.7",
                "sha": "abc123def456abc123def456abc123def456abcd",
            }
            return httpx.Response(
                201,
                json={
                    "ref": "refs/tags/v0.7.7",
                    "object": {"sha": "abc123def456abc123def456abc123def456abcd"},
                },
                request=request,
            )
        if request.method == "POST" and request.url.path.endswith("/releases"):
            return httpx.Response(
                201,
                json={
                    "id": 20,
                    "tag_name": "v0.7.7",
                    "name": "Release v0.7.7",
                    "body": "Release notes",
                    "draft": True,
                    "html_url": "https://github.com/example/demo-repository/releases/tag/v0.7.7",
                    "assets_url": "https://api.github.com/repos/example/demo-repository/releases/20/assets",
                    "upload_url": "https://uploads.github.com/repos/example/demo-repository/releases/20/assets{?name,label}",
                },
                request=request,
            )
        if request.method == "GET" and request.url.path.endswith("/releases/20/assets"):
            return httpx.Response(200, json=[], request=request)
        return httpx.Response(500, json={"message": "unexpected request"}, request=request)

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def fake_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    httpx.Client = fake_client
    try:
        result = GitHubReleaseClient("token").create_draft_release(
            repository=GitHubRepositoryRef(owner="example", repo="demo-repository"),
            tag_name="v0.7.7",
            title="Release v0.7.7",
            body="Release notes",
            target_commitish="abc123def456abc123def456abc123def456abcd",
            prerelease=False,
        )
    finally:
        httpx.Client = original_client

    assert result.remote_tag_created is True
    assert result.release_url.endswith("/releases/tag/v0.7.7")
    assert requests.index(("POST", "/repos/example/demo-repository/git/refs")) < requests.index(
        ("POST", "/repos/example/demo-repository/releases")
    )


def test_publish_github_repository_creates_remote_and_pushes(
    app_client,
    auth_headers,
    git_repository,
    tmp_path,
):
    import subprocess

    from app.schemas.settings import UpdateGitHubSettingsRequest
    from app.services.github_release_service import GitHubCreatedRepositoryResult

    bare = tmp_path / "created-remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(bare)],
        check=True,
        capture_output=True,
        text=True,
    )

    app_client.app.state.settings_service.update_github_settings(
        UpdateGitHubSettingsRequest(token="github-token")
    )

    calls = []

    class FakeGitHubReleaseClient:
        def __init__(self, token: str) -> None:
            calls.append({"token": token})

        def create_repository(self, *, name, description, private):
            calls.append({"name": name, "description": description, "private": private})
            return GitHubCreatedRepositoryResult(
                owner="example",
                repo=name,
                html_url=f"https://github.com/example/{name}",
                clone_url=str(bare),
                private=private,
            )

    app_client.app.state.repository_service._github_release_client_factory = FakeGitHubReleaseClient

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repo_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repo_id}/github/repositories/publish",
        headers=auth_headers,
        json={
            "repositoryName": "demo-published",
            "description": "Demo repository",
            "private": True,
            "commitMessage": "Publish demo repository",
            "paths": ["README.md"],
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["repository"] == "example/demo-published"
    assert body["repositoryUrl"] == "https://github.com/example/demo-published"
    assert body["branch"] == "main"
    assert body["snapshot"]["upstreamBranch"] == "origin/main"
    assert body["snapshot"]["ahead"] == 0
    assert calls[0]["token"] == "github-token"
    assert calls[1] == {"name": "demo-published", "description": "Demo repository", "private": True}

    remote_url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert remote_url == str(bare)
    remote_head = subprocess.run(
        ["git", "ls-remote", str(bare), "refs/heads/main"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "refs/heads/main" in remote_head


def test_publish_github_repository_blocks_existing_remote(
    app_client,
    auth_headers,
    git_repository_with_remote,
):
    from app.schemas.settings import UpdateGitHubSettingsRequest

    app_client.app.state.settings_service.update_github_settings(
        UpdateGitHubSettingsRequest(token="github-token")
    )

    class FakeGitHubReleaseClient:
        def __init__(self, token: str) -> None:
            raise AssertionError("GitHub client should not be created when a remote already exists.")

    app_client.app.state.repository_service._github_release_client_factory = FakeGitHubReleaseClient

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository_with_remote)},
    )
    assert register.status_code == 200, register.json()
    repo_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repo_id}/github/repositories/publish",
        headers=auth_headers,
        json={
            "repositoryName": "already-remote",
            "description": "",
            "private": False,
            "commitMessage": "Initial commit",
            "paths": [],
        },
    )

    assert response.status_code == 422
    assert "already has a remote" in response.json()["detail"]


def test_draft_github_release_explains_non_github_provider(
    app_client,
    auth_headers,
    git_repository,
    tmp_path,
):
    import subprocess

    from app.schemas.settings import UpdateGitHubSettingsRequest

    subprocess.run(
        ["git", "remote", "add", "origin", "https://gitlab.com/example/demo-repository.git"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    app_client.app.state.settings_service.update_github_settings(
        UpdateGitHubSettingsRequest(token="github-token")
    )
    asset = tmp_path / "AI Git Assistant_0.4.3_x64-setup.exe"
    asset.write_bytes(b"installer")

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/github/releases/draft",
        headers=auth_headers,
        json={
            "tagName": "v0.4.3",
            "title": "v0.4.3 - Phase D.3",
            "body": "Release notes",
            "assetPath": str(asset),
            "prerelease": False,
        },
    )

    assert response.status_code == 422, response.json()
    detail = response.json()["detail"]
    assert "GitHub platform actions are not available" in detail
    assert "origin: GitLab (gitlab.com)" in detail
    assert "Local Git features still work" not in detail


def test_draft_github_pull_request_uses_configured_token(
    app_client,
    auth_headers,
    git_repository,
    monkeypatch,
):
    import subprocess

    from app.schemas.settings import UpdateGitHubSettingsRequest
    from app.services.github_release_service import GitHubDraftPullRequestResult

    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/example/demo-repository.git"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "README.md"], cwd=git_repository, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Refresh README"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "switch", "-c", "feature/readme"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    (git_repository / "feature.txt").write_text("feature\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature.txt"], cwd=git_repository, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add feature note"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )

    app_client.app.state.settings_service.update_github_settings(
        UpdateGitHubSettingsRequest(token="github-token")
    )

    branch_checks: list[dict] = []

    def fake_remote_branch_exists(self, remote, branch, **kwargs):
        branch_checks.append({"remote": remote, "branch": branch, **kwargs})
        return remote == "origin" and branch == "feature/readme"

    monkeypatch.setattr(
        "app.services.repository_service.GitClient.remote_branch_exists",
        fake_remote_branch_exists,
    )

    calls: list[dict] = []

    class FakeGitHubReleaseClient:
        def __init__(self, token: str) -> None:
            self.token = token

        def create_draft_pull_request(self, **kwargs):
            calls.append({"token": self.token, **kwargs})
            return GitHubDraftPullRequestResult(
                number=12,
                pull_request_url="https://github.com/example/demo-repository/pull/12",
                title=kwargs["title"],
            )

    app_client.app.state.repository_service._github_release_client_factory = FakeGitHubReleaseClient

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/github/pull-requests/draft",
        headers=auth_headers,
        json={
            "baseBranch": "master",
            "title": "Add feature note",
            "body": "Summary\n- Adds a feature note.",
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["repository"] == "example/demo-repository"
    assert body["pullRequestUrl"].endswith("/pull/12")
    assert body["baseBranch"] == "master"
    assert body["headBranch"] == "feature/readme"
    assert "feature.txt" in body["content"]
    assert calls[0]["token"] == "github-token"
    assert calls[0]["repository"].slug == "example/demo-repository"
    assert calls[0]["head"] == "feature/readme"
    assert calls[0]["base"] == "master"
    assert branch_checks[0]["http_auth"].username == "x-access-token"
    assert branch_checks[0]["http_auth"].password == "github-token"


def test_draft_github_pull_request_blocks_unpushed_commits(
    app_client,
    auth_headers,
    git_repository,
    monkeypatch,
):
    import subprocess

    from app.schemas.settings import UpdateGitHubSettingsRequest

    repo = git_repository
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/example/demo-repository.git"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "bootstrap main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "switch", "-c", "feature/unpushed"], cwd=repo, check=True, capture_output=True)
    (repo / "local.txt").write_text("local\n", encoding="utf-8")
    subprocess.run(["git", "add", "local.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Local only"], cwd=repo, check=True, capture_output=True)

    app_client.app.state.settings_service.update_github_settings(
        UpdateGitHubSettingsRequest(token="github-token")
    )
    monkeypatch.setattr(
        "app.services.repository_service.GitClient.remote_branch_exists",
        lambda self, remote, branch, **kwargs: False,
    )

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/github/pull-requests/draft",
        headers=auth_headers,
        json={"baseBranch": "master", "title": "Local only", "body": ""},
    )

    assert response.status_code == 422, response.json()
    assert "Push the branch first" in response.json()["detail"]


def test_github_review_status_reads_open_pull_request(
    app_client,
    auth_headers,
    git_repository,
):
    import subprocess

    from app.schemas.settings import UpdateGitHubSettingsRequest
    from app.services.github_release_service import GitHubPullRequestStatusResult

    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/example/demo-repository.git"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "switch", "-c", "feature/review"], cwd=git_repository, check=True, capture_output=True)

    app_client.app.state.settings_service.update_github_settings(
        UpdateGitHubSettingsRequest(token="github-token")
    )

    calls: list[dict] = []

    class FakeGitHubReleaseClient:
        def __init__(self, token: str) -> None:
            self.token = token

        def get_pull_request_status(self, **kwargs):
            calls.append({"token": self.token, **kwargs})
            return GitHubPullRequestStatusResult(
                number=12,
                url="https://github.com/example/demo-repository/pull/12",
                title="Add review status",
                state="open",
                draft=False,
                base_branch="main",
                head_branch=kwargs["head_branch"],
                head_sha="abcdef1234567890",
                ci_status="success",
                review_summary="1 approved",
                review_count=1,
                comment_count=2,
                latest_comments=("reviewer: Looks good", "ci-bot: Checks passed"),
            )

    app_client.app.state.repository_service._github_release_client_factory = FakeGitHubReleaseClient

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "review_status"},
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["title"] == "Review Status"
    assert "Provider: GitHub" in body["content"]
    assert "Change request: #12 Add review status" in body["content"]
    assert "CI/check status: success" in body["content"]
    assert "reviewer: Looks good" in body["content"]
    assert calls[0]["token"] == "github-token"
    assert calls[0]["repository"].slug == "example/demo-repository"
    assert calls[0]["head_branch"] == "feature/review"


def test_draft_gitlab_merge_request_uses_configured_token(
    app_client,
    auth_headers,
    git_repository,
    monkeypatch,
):
    import subprocess

    from app.schemas.settings import UpdateGitLabSettingsRequest
    from app.services.gitlab_merge_request_service import GitLabDraftMergeRequestResult

    subprocess.run(
        ["git", "remote", "add", "origin", "https://gitlab.com/example/demo-repository.git"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "README.md"], cwd=git_repository, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Refresh README"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "switch", "-c", "feature/gitlab"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    (git_repository / "gitlab.txt").write_text("gitlab\n", encoding="utf-8")
    subprocess.run(["git", "add", "gitlab.txt"], cwd=git_repository, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add GitLab note"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )

    app_client.app.state.settings_service.update_gitlab_settings(
        UpdateGitLabSettingsRequest(token="gitlab-token", base_url="https://gitlab.com")
    )
    monkeypatch.setattr(
        "app.services.repository_service.GitClient.remote_branch_exists",
        lambda self, remote, branch, **kwargs: remote == "origin" and branch == "feature/gitlab",
    )

    calls: list[dict] = []

    class FakeGitLabMergeRequestClient:
        def __init__(self, token: str, *, base_url: str | None = None) -> None:
            self.token = token
            self.base_url = base_url

        def create_draft_merge_request(self, **kwargs):
            calls.append({"token": self.token, "base_url": self.base_url, **kwargs})
            return GitLabDraftMergeRequestResult(
                number=8,
                merge_request_url="https://gitlab.com/example/demo-repository/-/merge_requests/8",
                title=kwargs["title"],
            )

    app_client.app.state.repository_service._gitlab_merge_request_client_factory = FakeGitLabMergeRequestClient

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/gitlab/merge-requests/draft",
        headers=auth_headers,
        json={
            "baseBranch": "master",
            "title": "Add GitLab note",
            "body": "Summary\n- Adds a GitLab note.",
        },
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["repository"] == "example/demo-repository"
    assert body["mergeRequestUrl"].endswith("/merge_requests/8")
    assert body["baseBranch"] == "master"
    assert body["headBranch"] == "feature/gitlab"
    assert "gitlab.txt" in body["content"]
    assert calls[0]["token"] == "gitlab-token"
    assert calls[0]["base_url"] == "https://gitlab.com"
    assert calls[0]["repository"].slug == "example/demo-repository"
    assert calls[0]["source_branch"] == "feature/gitlab"
    assert calls[0]["target_branch"] == "master"


def test_gitlab_review_status_reads_open_merge_request(
    app_client,
    auth_headers,
    git_repository,
):
    import subprocess

    from app.schemas.settings import UpdateGitLabSettingsRequest
    from app.services.gitlab_merge_request_service import GitLabMergeRequestStatusResult

    subprocess.run(
        ["git", "remote", "add", "origin", "https://gitlab.com/example/demo-repository.git"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "switch", "-c", "feature/gitlab-review"], cwd=git_repository, check=True, capture_output=True)

    app_client.app.state.settings_service.update_gitlab_settings(
        UpdateGitLabSettingsRequest(token="gitlab-token", base_url="https://gitlab.com")
    )

    calls: list[dict] = []

    class FakeGitLabMergeRequestClient:
        def __init__(self, token: str, *, base_url: str | None = None) -> None:
            self.token = token
            self.base_url = base_url

        def get_merge_request_status(self, **kwargs):
            calls.append({"token": self.token, "base_url": self.base_url, **kwargs})
            return GitLabMergeRequestStatusResult(
                number=8,
                url="https://gitlab.com/example/demo-repository/-/merge_requests/8",
                title="Add GitLab review status",
                state="opened",
                draft=True,
                base_branch="main",
                head_branch=kwargs["source_branch"],
                head_sha="123456abcdef7890",
                ci_status="pending",
                review_summary="no approval signal",
                review_count=0,
                comment_count=1,
                latest_comments=("reviewer: Please add tests",),
            )

    app_client.app.state.repository_service._gitlab_merge_request_client_factory = FakeGitLabMergeRequestClient

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "review_status"},
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert "Provider: GitLab" in body["content"]
    assert "Change request: !8 Add GitLab review status" in body["content"]
    assert "CI/check status: pending" in body["content"]
    assert "reviewer: Please add tests" in body["content"]
    assert calls[0]["token"] == "gitlab-token"
    assert calls[0]["base_url"] == "https://gitlab.com"
    assert calls[0]["repository"].slug == "example/demo-repository"
    assert calls[0]["source_branch"] == "feature/gitlab-review"


def test_github_release_permission_error_is_actionable():
    import httpx
    import pytest

    from app.errors import ValidationFailure
    from app.services.github_release_service import GitHubReleaseClient

    response = httpx.Response(
        403,
        json={"message": "Resource not accessible by personal access token"},
        request=httpx.Request("POST", "https://api.github.com/repos/example/repo/releases"),
    )

    with pytest.raises(ValidationFailure) as exc:
        GitHubReleaseClient._raise_for_github_error(response)

    assert "Contents: Read and write" in exc.value.message
    assert "Settings" in exc.value.message


def test_write_plan_includes_risk_and_local_privacy_receipt(
    app_client,
    auth_headers,
    git_repository,
):
    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": 'commit README.md with message "Update README"'},
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["requiresConfirmation"] is True
    assert body["risk"]["level"] in {"low", "medium"}
    assert body["privacyReceipt"]["externalProvider"] is False
    assert "No external AI provider" in body["privacyReceipt"]["exactContext"]


def test_execute_merge_conflict_then_guided_resolution(
    app_client,
    auth_headers,
    git_repository,
):
    import subprocess

    repo = git_repository

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    git("restore", "README.md")
    base_branch = git("branch", "--show-current")
    git("checkout", "-b", "feature/conflict")
    (repo / "README.md").write_text("# Demo\n\nFeature branch.\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "feature edit")
    git("checkout", base_branch)
    (repo / "README.md").write_text("# Demo\n\nMain branch.\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "main edit")

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    merge_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "merge feature/conflict"},
    )
    assert merge_plan_response.status_code == 200, merge_plan_response.json()
    merge_plan = merge_plan_response.json()
    assert merge_plan["steps"][0]["kind"] == "merge"

    merge_response = app_client.post(
        f"/v1/repositories/{repository_id}/execute-plan",
        headers=auth_headers,
        json={"planId": merge_plan["planId"]},
    )
    assert merge_response.status_code == 400, merge_response.json()
    assert "Merge stopped with conflicts" in merge_response.json()["detail"]

    conflicts_response = app_client.post(
        f"/v1/repositories/{repository_id}/read-actions",
        headers=auth_headers,
        json={"action": "conflicts"},
    )
    assert conflicts_response.status_code == 200, conflicts_response.json()
    assert "README.md" in conflicts_response.json()["content"]
    assert "<<<<<<<" in conflicts_response.json()["content"]

    (repo / "README.md").write_text(
        "# Demo\n\nMain branch.\nFeature branch.\n",
        encoding="utf-8",
    )
    stage_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "stage README.md"},
    )
    assert stage_plan_response.status_code == 200, stage_plan_response.json()
    stage_plan = stage_plan_response.json()
    assert stage_plan["steps"][0]["kind"] == "stage"

    stage_response = app_client.post(
        f"/v1/repositories/{repository_id}/execute-plan",
        headers=auth_headers,
        json={"planId": stage_plan["planId"]},
    )
    assert stage_response.status_code == 200, stage_response.json()

    continue_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "continue merge"},
    )
    assert continue_plan_response.status_code == 200, continue_plan_response.json()
    continue_plan = continue_plan_response.json()
    assert continue_plan["steps"][0]["kind"] == "merge_commit"

    continue_response = app_client.post(
        f"/v1/repositories/{repository_id}/execute-plan",
        headers=auth_headers,
        json={"planId": continue_plan["planId"]},
    )
    assert continue_response.status_code == 200, continue_response.json()
    assert continue_response.json()["title"] == "Merge completed"
    assert continue_response.json()["snapshot"]["conflicts"] == []


def test_preview_and_apply_conflict_resolution_keep_local(
    app_client,
    auth_headers,
    git_repository,
):
    import subprocess

    repo = git_repository

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    git("restore", "README.md")
    base_branch = git("branch", "--show-current")
    git("checkout", "-b", "feature/conflict")
    (repo / "README.md").write_text("# Demo\n\nFeature branch.\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "feature edit")
    git("checkout", base_branch)
    (repo / "README.md").write_text("# Demo\n\nMain branch.\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "main edit")

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    merge_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "merge feature/conflict"},
    )
    assert merge_plan_response.status_code == 200, merge_plan_response.json()
    merge_plan = merge_plan_response.json()
    merge_response = app_client.post(
        f"/v1/repositories/{repository_id}/execute-plan",
        headers=auth_headers,
        json={"planId": merge_plan["planId"]},
    )
    assert merge_response.status_code == 400, merge_response.json()

    preview = app_client.post(
        f"/v1/repositories/{repository_id}/conflicts/preview-resolution",
        headers=auth_headers,
        json={"strategy": "ours", "paths": ["README.md"]},
    )
    assert preview.status_code == 200, preview.json()
    preview_body = preview.json()
    assert preview_body["resolvedFiles"][0]["path"] == "README.md"
    assert "Main branch." in preview_body["resolvedFiles"][0]["content"]
    assert "<<<<<<<" not in preview_body["resolvedFiles"][0]["content"]

    apply = app_client.post(
        f"/v1/repositories/{repository_id}/conflicts/apply-resolution",
        headers=auth_headers,
        json={
            "strategy": "ours",
            "resolvedFiles": preview_body["resolvedFiles"],
        },
    )
    assert apply.status_code == 200, apply.json()
    assert apply.json()["snapshot"]["conflicts"] == []
    assert "<<<<<<<" not in (repo / "README.md").read_text(encoding="utf-8")

    continue_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "continue merge"},
    )
    assert continue_plan_response.status_code == 200, continue_plan_response.json()
    continue_response = app_client.post(
        f"/v1/repositories/{repository_id}/execute-plan",
        headers=auth_headers,
        json={"planId": continue_plan_response.json()["planId"]},
    )
    assert continue_response.status_code == 200, continue_response.json()
    assert continue_response.json()["title"] == "Merge completed"


def test_preview_and_apply_markerless_resolved_conflict(
    app_client,
    auth_headers,
    git_repository,
):
    import subprocess

    repo = git_repository

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    git("restore", "README.md")
    base_branch = git("branch", "--show-current")
    git("checkout", "-b", "feature/markerless-conflict")
    (repo / "README.md").write_text("# Demo\n\nFeature branch.\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "feature markerless edit")
    git("checkout", base_branch)
    (repo / "README.md").write_text("# Demo\n\nMain branch.\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "main markerless edit")

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    merge_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "merge feature/markerless-conflict"},
    )
    assert merge_plan_response.status_code == 200, merge_plan_response.json()
    merge_response = app_client.post(
        f"/v1/repositories/{repository_id}/execute-plan",
        headers=auth_headers,
        json={"planId": merge_plan_response.json()["planId"]},
    )
    assert merge_response.status_code == 400, merge_response.json()

    (repo / "README.md").write_text("# Demo\n\nResolved manually.\n", encoding="utf-8")

    preview = app_client.post(
        f"/v1/repositories/{repository_id}/conflicts/preview-resolution",
        headers=auth_headers,
        json={"strategy": "ai", "paths": ["README.md"]},
    )
    assert preview.status_code == 200, preview.json()
    preview_body = preview.json()
    assert preview_body["resolvedFiles"][0]["conflictCount"] == 0
    assert "manually resolved" in preview_body["resolvedFiles"][0]["summary"]
    assert "Resolved manually." in preview_body["resolvedFiles"][0]["content"]

    apply = app_client.post(
        f"/v1/repositories/{repository_id}/conflicts/apply-resolution",
        headers=auth_headers,
        json={
            "strategy": "ai",
            "resolvedFiles": preview_body["resolvedFiles"],
        },
    )
    assert apply.status_code == 200, apply.json()
    assert apply.json()["snapshot"]["conflicts"] == []

    continue_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "continue merge"},
    )
    assert continue_plan_response.status_code == 200, continue_plan_response.json()


def test_execute_stash_apply_and_drop_specific_ref(
    app_client,
    auth_headers,
    git_repository,
):
    import subprocess

    subprocess.run(
        ["git", "stash", "push", "-m", "phase-c-apply"],
        cwd=git_repository,
        check=True,
        capture_output=True,
        text=True,
    )

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repository_id = register.json()["id"]

    apply_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "apply stash stash@{0}"},
    )
    assert apply_plan_response.status_code == 200, apply_plan_response.json()
    apply_plan = apply_plan_response.json()
    assert apply_plan["steps"][0]["kind"] == "stash_apply"
    assert apply_plan["steps"][0]["stashRef"] == "stash@{0}"

    apply_response = app_client.post(
        f"/v1/repositories/{repository_id}/execute-plan",
        headers=auth_headers,
        json={"planId": apply_plan["planId"]},
    )
    assert apply_response.status_code == 200, apply_response.json()
    assert apply_response.json()["title"] == "Stash applied"
    assert "Changed." in (git_repository / "README.md").read_text(encoding="utf-8")

    drop_plan_response = app_client.post(
        f"/v1/repositories/{repository_id}/resolve-local",
        headers=auth_headers,
        json={"message": "drop stash stash@{0}"},
    )
    assert drop_plan_response.status_code == 200, drop_plan_response.json()
    drop_plan = drop_plan_response.json()
    assert drop_plan["steps"][0]["kind"] == "stash_drop"

    drop_response = app_client.post(
        f"/v1/repositories/{repository_id}/execute-plan",
        headers=auth_headers,
        json={"planId": drop_plan["planId"]},
    )
    assert drop_response.status_code == 200, drop_response.json()
    assert drop_response.json()["title"] == "Stash dropped"


# ---------------------------------------------------------------------------
# Execute-plan: commit + push with pre-configured upstream (cloned repo)
# ---------------------------------------------------------------------------

def test_execute_commit_and_push_with_upstream(
    app_client,
    auth_headers,
    git_repository_with_remote,
):
    repo = git_repository_with_remote

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    assert register.status_code == 200, register.json()
    repo_id = register.json()["id"]

    plan_resp = app_client.post(
        f"/v1/repositories/{repo_id}/resolve-local",
        headers=auth_headers,
        json={"message": 'Commit login.py with message "Add login stub", then push to main'},
    )
    assert plan_resp.status_code == 200, plan_resp.json()
    plan = plan_resp.json()
    assert plan["planKind"] == "write"
    assert plan["requiresConfirmation"] is True
    assert [s["kind"] for s in plan["steps"]] == ["stage", "commit", "push"]
    push_step = plan["steps"][2]
    assert push_step["remote"] == "origin"
    assert push_step["branch"] == "main"
    assert push_step["setUpstream"] is False

    exec_resp = app_client.post(
        f"/v1/repositories/{repo_id}/execute-plan",
        headers=auth_headers,
        json={"planId": plan["planId"]},
    )
    assert exec_resp.status_code == 200, exec_resp.json()
    result = exec_resp.json()
    assert result["title"] == "Commit and push completed"
    assert result["snapshot"]["ahead"] == 0


# ---------------------------------------------------------------------------
# Execute-plan: commit + push for a new local branch (no upstream yet)
# ---------------------------------------------------------------------------

def test_execute_commit_and_push_sets_upstream_for_new_branch(
    app_client,
    auth_headers,
    git_repository_with_remote,
):
    import subprocess

    repo = git_repository_with_remote

    # Make an initial commit on main so the remote is non-empty, then create
    # a new local branch that has never been pushed.
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "bootstrap main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "-b", "dev_1"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    assert register.status_code == 200, register.json()
    repo_id = register.json()["id"]

    plan_resp = app_client.post(
        f"/v1/repositories/{repo_id}/resolve-local",
        headers=auth_headers,
        json={"message": 'Commit login.py with message "Add login stub", then push to dev_1'},
    )
    assert plan_resp.status_code == 200, plan_resp.json()
    plan = plan_resp.json()
    assert plan["planKind"] == "write"
    assert plan["requiresConfirmation"] is True
    push_step = plan["steps"][-1]
    assert push_step["kind"] == "push"
    assert push_step["remote"] == "origin"
    assert push_step["branch"] == "dev_1"
    assert push_step["setUpstream"] is True

    exec_resp = app_client.post(
        f"/v1/repositories/{repo_id}/execute-plan",
        headers=auth_headers,
        json={"planId": plan["planId"]},
    )
    assert exec_resp.status_code == 200, exec_resp.json()
    result = exec_resp.json()
    assert result["title"] == "Commit and push completed"
    # After --set-upstream push the branch should now track origin/dev_1.
    assert result["snapshot"]["upstreamBranch"] == "origin/dev_1"


# ---------------------------------------------------------------------------
# Execute-plan: standalone push on a branch that already has upstream
# ---------------------------------------------------------------------------

def test_execute_standalone_push(
    app_client,
    auth_headers,
    git_repository_with_remote,
):
    import subprocess

    repo = git_repository_with_remote

    # Push an empty commit to establish origin/main so Git can compute
    # ahead/behind counts, then make another local-only commit to push.
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "bootstrap main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "login.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "local commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    assert register.status_code == 200, register.json()
    repo_id = register.json()["id"]

    plan_resp = app_client.post(
        f"/v1/repositories/{repo_id}/resolve-local",
        headers=auth_headers,
        json={"message": "push"},
    )
    assert plan_resp.status_code == 200, plan_resp.json()
    plan = plan_resp.json()
    assert plan["planKind"] == "write"
    assert plan["requiresConfirmation"] is True
    assert plan["steps"][0]["kind"] == "push"

    exec_resp = app_client.post(
        f"/v1/repositories/{repo_id}/execute-plan",
        headers=auth_headers,
        json={"planId": plan["planId"]},
    )
    assert exec_resp.status_code == 200, exec_resp.json()
    assert exec_resp.json()["title"] == "Push completed"
    assert exec_resp.json()["snapshot"]["ahead"] == 0


# ---------------------------------------------------------------------------
# Plan cancel
# ---------------------------------------------------------------------------

def test_execute_pull(app_client, auth_headers, git_repository_behind_remote):
    repo = git_repository_behind_remote

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    assert register.status_code == 200, register.json()
    repo_id = register.json()["id"]

    plan_resp = app_client.post(
        f"/v1/repositories/{repo_id}/resolve-local",
        headers=auth_headers,
        json={"message": "pull"},
    )
    assert plan_resp.status_code == 200, plan_resp.json()
    plan = plan_resp.json()
    assert plan["planKind"] == "write"
    assert plan["steps"][0]["kind"] == "pull"
    assert plan["steps"][0]["behind"] == 1

    exec_resp = app_client.post(
        f"/v1/repositories/{repo_id}/execute-plan",
        headers=auth_headers,
        json={"planId": plan["planId"]},
    )
    assert exec_resp.status_code == 200, exec_resp.json()
    result = exec_resp.json()
    assert result["title"] == "Pull completed"
    assert result["snapshot"]["behind"] == 0


def test_execute_create_and_switch_branch(app_client, auth_headers, git_repository_with_remote):
    import subprocess
    repo = git_repository_with_remote

    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True, capture_output=True)

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    assert register.status_code == 200, register.json()
    repo_id = register.json()["id"]

    # create branch
    create_resp = app_client.post(
        f"/v1/repositories/{repo_id}/resolve-local",
        headers=auth_headers,
        json={"message": "create branch feature/auth"},
    )
    assert create_resp.status_code == 200, create_resp.json()
    create_plan = create_resp.json()
    assert create_plan["planKind"] == "write"
    assert create_plan["steps"][0]["branch"] == "feature/auth"

    exec_resp = app_client.post(
        f"/v1/repositories/{repo_id}/execute-plan",
        headers=auth_headers,
        json={"planId": create_plan["planId"]},
    )
    assert exec_resp.status_code == 200, exec_resp.json()
    assert exec_resp.json()["snapshot"]["branch"] == "feature/auth"

    # switch back to main
    switch_resp = app_client.post(
        f"/v1/repositories/{repo_id}/resolve-local",
        headers=auth_headers,
        json={"message": "switch to main"},
    )
    assert switch_resp.status_code == 200, switch_resp.json()
    switch_plan = switch_resp.json()
    assert switch_plan["planKind"] == "write"

    exec_switch = app_client.post(
        f"/v1/repositories/{repo_id}/execute-plan",
        headers=auth_headers,
        json={"planId": switch_plan["planId"]},
    )
    assert exec_switch.status_code == 200, exec_switch.json()
    assert exec_switch.json()["snapshot"]["branch"] == "main"


def test_cancel_plan_removes_pending_plan(
    app_client,
    auth_headers,
    git_repository_with_remote,
):
    repo = git_repository_with_remote

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    repo_id = register.json()["id"]

    plan_resp = app_client.post(
        f"/v1/repositories/{repo_id}/resolve-local",
        headers=auth_headers,
        json={"message": 'Commit login.py with message "Add login stub"'},
    )
    plan_id = plan_resp.json()["planId"]

    cancel_resp = app_client.post(
        f"/v1/repositories/{repo_id}/cancel-plan",
        headers=auth_headers,
        json={"planId": plan_id},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["cancelled"] is True

    # Executing a cancelled plan must fail.
    exec_resp = app_client.post(
        f"/v1/repositories/{repo_id}/execute-plan",
        headers=auth_headers,
        json={"planId": plan_id},
    )
    assert exec_resp.status_code == 422


def test_create_compare_and_abandon_agent_session(app_client, auth_headers, git_repository):
    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(git_repository)},
    )
    assert register.status_code == 200, register.json()
    repo_id = register.json()["id"]

    create = app_client.post(
        f"/v1/repositories/{repo_id}/agent-sessions",
        headers=auth_headers,
        json={"task": "try isolated docs change"},
    )

    assert create.status_code == 200, create.json()
    session = create.json()
    assert session["status"] == "active"
    assert session["branchName"].startswith("agent/")
    assert session["baseBranch"]

    from pathlib import Path

    worktree_path = Path(session["worktreePath"])
    assert worktree_path.exists()

    listed = app_client.get(
        f"/v1/repositories/{repo_id}/agent-sessions",
        headers=auth_headers,
    )
    assert listed.status_code == 200, listed.json()
    assert listed.json()[0]["id"] == session["id"]

    compare = app_client.get(
        f"/v1/repositories/{repo_id}/agent-sessions/{session['id']}/compare",
        headers=auth_headers,
    )
    assert compare.status_code == 200, compare.json()
    assert "try isolated docs change" in compare.json()["content"]

    abandon = app_client.post(
        f"/v1/repositories/{repo_id}/agent-sessions/{session['id']}/abandon",
        headers=auth_headers,
    )
    assert abandon.status_code == 200, abandon.json()
    assert abandon.json()["session"]["status"] == "abandoned"
    assert not worktree_path.exists()


def test_merge_agent_session_into_repository(app_client, auth_headers, git_repository):
    import subprocess
    from pathlib import Path

    repo = git_repository
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Prepare clean main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    register = app_client.post(
        "/v1/repositories/register",
        headers=auth_headers,
        json={"path": str(repo)},
    )
    assert register.status_code == 200, register.json()
    repo_id = register.json()["id"]

    create = app_client.post(
        f"/v1/repositories/{repo_id}/agent-sessions",
        headers=auth_headers,
        json={"task": "add isolated agent note"},
    )
    assert create.status_code == 200, create.json()
    session = create.json()
    worktree = Path(session["worktreePath"])

    (worktree / "agent-note.txt").write_text("agent note\n", encoding="utf-8")
    subprocess.run(["git", "add", "agent-note.txt"], cwd=worktree, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add agent note"],
        cwd=worktree,
        check=True,
        capture_output=True,
    )

    compare = app_client.get(
        f"/v1/repositories/{repo_id}/agent-sessions/{session['id']}/compare",
        headers=auth_headers,
    )
    assert compare.status_code == 200, compare.json()
    assert compare.json()["session"]["commitsAhead"] == 1
    assert "agent-note.txt" in compare.json()["content"]

    merge = app_client.post(
        f"/v1/repositories/{repo_id}/agent-sessions/{session['id']}/merge",
        headers=auth_headers,
    )
    assert merge.status_code == 200, merge.json()
    assert merge.json()["session"]["status"] == "merged"
    assert (repo / "agent-note.txt").read_text(encoding="utf-8") == "agent note\n"
