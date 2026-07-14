use serde::{Deserialize, Serialize};
use tauri::State;

use crate::{
    app_state::AppState,
    models::{
        repositories::Repository,
        settings::{
            GitHubSettings, GitLabSettings, LLMSettings, SetExternalLLMRequest,
            UpdateGitHubSettingsRequest, UpdateGitLabSettingsRequest, UpdateLLMSettingsRequest,
        },
    },
    sidecar_proxy::SidecarProxy,
};

#[derive(Debug, Serialize, Deserialize)]
pub struct LLMTestResult {
    pub ok: bool,
    pub message: String,
}

#[tauri::command(rename_all = "camelCase")]
pub async fn get_llm_settings(
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<LLMSettings, String> {
    proxy.get(&state, "/v1/settings/llm").await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn update_llm_settings(
    request: UpdateLLMSettingsRequest,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<LLMSettings, String> {
    proxy.put(&state, "/v1/settings/llm", &request).await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn get_github_settings(
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<GitHubSettings, String> {
    proxy.get(&state, "/v1/settings/github").await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn update_github_settings(
    request: UpdateGitHubSettingsRequest,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<GitHubSettings, String> {
    proxy.put(&state, "/v1/settings/github", &request).await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn get_gitlab_settings(
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<GitLabSettings, String> {
    proxy.get(&state, "/v1/settings/gitlab").await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn update_gitlab_settings(
    request: UpdateGitLabSettingsRequest,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<GitLabSettings, String> {
    proxy.put(&state, "/v1/settings/gitlab", &request).await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn test_llm_connection(
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<LLMTestResult, String> {
    proxy.post(&state, "/v1/settings/llm/test", &serde_json::Value::Null).await
}

#[tauri::command(rename_all = "camelCase")]
pub async fn set_repository_llm_allowed(
    repository_id: String,
    allowed: bool,
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<Repository, String> {
    let payload = SetExternalLLMRequest { allowed };
    proxy
        .post(
            &state,
            &format!("/v1/repositories/{repository_id}/set-llm"),
            &payload,
        )
        .await
}
