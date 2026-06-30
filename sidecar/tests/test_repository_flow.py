from __future__ import annotations


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
