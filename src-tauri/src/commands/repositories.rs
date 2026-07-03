use serde_json::json;
use tauri::{AppHandle, State};
use tauri_plugin_dialog::{DialogExt, FilePath};

use crate::{
    app_state::AppState,
    models::repositories::{
        ActionExecutionResult, CancelActionPlanResponse, FolderClassification, LocalActionPlan,
        DraftGitHubReleaseRequest, DraftGitHubReleaseResponse, GenerateChangeSummaryResponse,
        GenerateCommitMessageResponse, ReadActionRequest, ReadActionResult, Repository,
        RepositorySnapshot,
    },
    sidecar_proxy::SidecarProxy,
};

#[tauri::command(rename_all = "camelCase")]
pub async fn list_repositories(
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<Vec<Repository>, String> {
    proxy.get(&state, "/v1/repositories").await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn pick_and_classify_repository(
    app: AppHandle,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<Option<FolderClassification>, String> {
    let selected = app.dialog().file().blocking_pick_folder();
    let Some(selected) = selected else {
        return Ok(None);
    };

    let path = match selected {
        FilePath::Path(path) => path,
        FilePath::Url(_) => {
            return Err("The selected folder must be a local filesystem path.".to_owned());
        }
    };

    let payload = json!({ "path": path.to_string_lossy() });

    // This route only classifies the selected folder. It never registers a
    // repository, creates .git metadata, or modifies the selected folder.
    proxy
        .post(&state, "/v1/repositories/classify", &payload)
        .await
        .map(Some)
}

#[tauri::command(rename_all = "camelCase")]
pub async fn register_repository(
    path: String,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<Repository, String> {
    let payload = json!({ "path": path });

    proxy
        .post(&state, "/v1/repositories/register", &payload)
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn initialise_and_register_repository(
    path: String,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<Repository, String> {
    // This command is called only after the React confirmation dialog is
    // accepted. The backend re-classifies the folder again before git init.
    let payload = json!({
        "path": path,
        "confirmed": true,
    });

    proxy
        .post(
            &state,
            "/v1/repositories/initialise-and-register",
            &payload,
        )
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn get_repository_snapshot(
    repository_id: String,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<RepositorySnapshot, String> {
    proxy
        .get(&state, &format!("/v1/repositories/{repository_id}/snapshot"))
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn run_read_action(
    repository_id: String,
    request: ReadActionRequest,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<ReadActionResult, String> {
    proxy
        .post(
            &state,
            &format!("/v1/repositories/{repository_id}/read-actions"),
            &request,
        )
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn resolve_local_request(
    repository_id: String,
    message: String,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<LocalActionPlan, String> {
    let payload = json!({ "message": message });
    proxy
        .post(
            &state,
            &format!("/v1/repositories/{repository_id}/resolve-local"),
            &payload,
        )
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn execute_action_plan(
    repository_id: String,
    plan_id: String,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<ActionExecutionResult, String> {
    let payload = json!({ "planId": plan_id });
    proxy
        .post(
            &state,
            &format!("/v1/repositories/{repository_id}/execute-plan"),
            &payload,
        )
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn cancel_action_plan(
    repository_id: String,
    plan_id: String,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<CancelActionPlanResponse, String> {
    let payload = json!({ "planId": plan_id });
    proxy
        .post(
            &state,
            &format!("/v1/repositories/{repository_id}/cancel-plan"),
            &payload,
        )
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn add_to_gitignore(
    repository_id: String,
    paths: Vec<String>,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<serde_json::Value, String> {
    let payload = json!({ "paths": paths });
    proxy
        .post(
            &state,
            &format!("/v1/repositories/{repository_id}/add-to-gitignore"),
            &payload,
        )
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn remove_repository(
    repository_id: String,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<(), String> {
    proxy
        .delete(&state, &format!("/v1/repositories/{repository_id}"))
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn pick_clone_target(app: AppHandle) -> Result<Option<String>, String> {
    let selected = app.dialog().file().blocking_pick_folder();
    Ok(selected.and_then(|fp| match fp {
        FilePath::Path(path) => Some(path.to_string_lossy().into_owned()),
        FilePath::Url(_) => None,
    }))
}

#[tauri::command(rename_all = "camelCase")]
pub async fn pick_release_asset(app: AppHandle) -> Result<Option<String>, String> {
    let selected = app.dialog().file().blocking_pick_file();
    Ok(selected.and_then(|fp| match fp {
        FilePath::Path(path) => Some(path.to_string_lossy().into_owned()),
        FilePath::Url(_) => None,
    }))
}

#[tauri::command(rename_all = "camelCase")]
pub async fn clone_repository(
    url: String,
    parent_path: String,
    folder_name: Option<String>,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<Repository, String> {
    let payload = json!({ "url": url, "parent_path": parent_path, "folder_name": folder_name });
    proxy.post(&state, "/v1/repositories/clone", &payload).await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn submit_action_plan(
    repository_id: String,
    steps: serde_json::Value,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<serde_json::Value, String> {
    let payload = json!({ "steps": steps });
    proxy
        .post(
            &state,
            &format!("/v1/repositories/{repository_id}/submit-plan"),
            &payload,
        )
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn generate_commit_message(
    repository_id: String,
    paths: Vec<String>,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<GenerateCommitMessageResponse, String> {
    let payload = json!({ "paths": paths });
    proxy
        .post(
            &state,
            &format!("/v1/repositories/{repository_id}/generate-commit-message"),
            &payload,
        )
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn generate_change_summary(
    repository_id: String,
    paths: Vec<String>,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<GenerateChangeSummaryResponse, String> {
    let payload = json!({ "paths": paths });
    proxy
        .post(
            &state,
            &format!("/v1/repositories/{repository_id}/generate-change-summary"),
            &payload,
        )
        .await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn draft_github_release(
    repository_id: String,
    request: DraftGitHubReleaseRequest,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<DraftGitHubReleaseResponse, String> {
    proxy
        .post(
            &state,
            &format!("/v1/repositories/{repository_id}/github/releases/draft"),
            &request,
        )
        .await
}
