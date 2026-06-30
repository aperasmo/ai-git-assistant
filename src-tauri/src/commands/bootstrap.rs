use tauri::State;

use crate::{
    app_state::AppState,
    models::bootstrap::{BootstrapStatus, DiagnosticsStatus, GitInstallationStatus},
    sidecar,
    sidecar_proxy::SidecarProxy,
};

#[tauri::command]
pub async fn get_bootstrap_status(
    state: State<'_, AppState>,
) -> Result<BootstrapStatus, String> {
    // Tauri async commands that borrow managed State must return Result.
    // Keeping this as Result gives the webview one consistent error channel
    // instead of allowing Rust-side failures to become opaque IPC errors.
    let runtime = state.runtime.lock().await;

    Ok(BootstrapStatus {
        sidecar_status: runtime.status.clone(),
        message: runtime.message.clone(),
        protocol_version: runtime.protocol_version.clone(),
    })
}

#[tauri::command]
pub async fn get_git_installation_status(
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<GitInstallationStatus, String> {
    sidecar::git_installation_status(&state, &proxy).await
}

#[tauri::command]
pub async fn get_diagnostics_status(
    state: State<'_, AppState>,
    proxy: State<'_, SidecarProxy>,
) -> Result<DiagnosticsStatus, String> {
    let mut diagnostics: DiagnosticsStatus = proxy.get(&state, "/v1/system/diagnostics").await?;
    diagnostics.recent_sidecar_messages = state.recent_sidecar_logs().await;
    Ok(diagnostics)
}
