use tauri::State;

use crate::{
    app_state::AppState,
    models::{
        repositories::Repository,
        settings::{LLMSettings, SetExternalLLMRequest, UpdateLLMSettingsRequest},
    },
    sidecar_proxy::SidecarProxy,
};

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
