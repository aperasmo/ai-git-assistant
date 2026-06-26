use std::time::Duration;

use serde::Deserialize;
use tauri::AppHandle;
use tauri_plugin_shell::{process::CommandEvent, ShellExt};
use uuid::Uuid;

use crate::{
    app_state::AppState,
    models::bootstrap::GitInstallationStatus,
    sidecar_proxy::SidecarProxy,
};

const READY_PREFIX: &str = "AIGA_READY:";

#[derive(Deserialize)]
struct ReadyMessage {
    port: u16,
    protocol_version: String,
}

// FastAPI serialises response fields as camelCase JSON, such as
// `protocolVersion`. Rust keeps snake_case field names internally, so
// Serde needs this rule when converting the JSON response into this struct.
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct HealthResponse {
    status: String,
    protocol_version: String,
    #[allow(dead_code)]
    service_version: String,
}

pub fn launch(app: AppHandle, state: AppState) {
    tauri::async_runtime::spawn(async move {
        state.starting().await;

        // A session token exists only in memory for this desktop-app session.
        // It is passed directly to the child process and is never exposed to React.
        let token = Uuid::new_v4().to_string() + &Uuid::new_v4().to_string();
        let sidecar = match app.shell().sidecar("ai-git-sidecar") {
            Ok(command) => command
                .env("AIGA_SESSION_TOKEN", &token)
                .env("AIGA_ENV", "production"),
            Err(error) => {
                state
                    .failed(format!("Unable to configure local service: {error}"))
                    .await;
                return;
            }
        };

        let (mut events, child) = match sidecar.spawn() {
            Ok(spawned) => spawned,
            Err(error) => {
                state
                    .failed(format!("Unable to start local service: {error}"))
                    .await;
                return;
            }
        };
        // Keep the child handle before waiting for readiness. A close request during
        // startup must still be able to terminate the process.
        state.store_sidecar_child(child).await;
        let proxy = match SidecarProxy::new() {
            Ok(proxy) => proxy,
            Err(message) => {
                state.failed(message).await;
                return;
            }
        };

        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    // Tauri exposes sidecar stdout as bytes, not String. Decode it
                    // strictly so malformed process output cannot be silently accepted.
                    let line = match std::str::from_utf8(&bytes) {
                        Ok(line) => line.trim(),
                        Err(_) => {
                            state
                                .failed("Local service returned non-UTF-8 startup output.")
                                .await;
                            return;
                        }
                    };

                    // stdout is reserved for one readiness event. Any other output
                    // is a protocol violation rather than something to ignore.
                    let Some(raw_payload) = line.strip_prefix(READY_PREFIX) else {
                        state
                            .failed("Local service returned an unexpected startup message.")
                            .await;
                        return;
                    };

                    let ready = match serde_json::from_str::<ReadyMessage>(raw_payload) {
                        Ok(ready) if ready.port > 0 && ready.protocol_version == "1" => ready,
                        Ok(_) => {
                            state
                                .failed("Local service returned an unsupported startup protocol.")
                                .await;
                            return;
                        }
                        Err(_) => {
                            state
                                .failed("Local service returned an invalid startup message.")
                                .await;
                            return;
                        }
                    };

                    // Rust retains both the loopback endpoint and token after this
                    // point. The React webview receives only typed command results.
                    let endpoint = format!("http://127.0.0.1:{}", ready.port);
                    state
                        .configure_sidecar(endpoint, token, ready.protocol_version)
                        .await;

                    // The process is not considered ready merely because it bound a
                    // port. It must also accept an authenticated health request.
                    for _ in 0..20 {
                        let health = proxy.get::<HealthResponse>(&state, "/v1/health").await;
                        if let Ok(response) = health {
                            if response.status == "ok" && response.protocol_version == "1" {
                                state.ready().await;
                                return;
                            }
                        }
                        tokio::time::sleep(Duration::from_millis(150)).await;
                    }

                    state
                        .failed("The local service started but did not pass authenticated health checks.")
                        .await;
                    return;
                }
                CommandEvent::Stderr(_) => {
                    // Stderr remains local. Never forward sidecar logs to the webview.
                }
                CommandEvent::Error(error) => {
                    state.failed(format!("Local service error: {error}")).await;
                    return;
                }
                CommandEvent::Terminated(payload) => {
                    state
                        .failed(format!(
                            "The local service stopped unexpectedly (exit code {:?}).",
                            payload.code
                        ))
                        .await;
                    return;
                }
                _ => {}
            }
        }

        state
            .failed("The local service stopped before completing startup.")
            .await;
    });
}

pub async fn git_installation_status(
    state: &AppState,
    proxy: &SidecarProxy,
) -> Result<GitInstallationStatus, String> {
    proxy.get(state, "/v1/system/git-installation").await
}


#[cfg(target_os = "windows")]
async fn force_stop_sidecar_tree(pid: u32) {
    use std::os::windows::process::CommandExt;

    const CREATE_NO_WINDOW: u32 = 0x0800_0000;

    let _ = tokio::task::spawn_blocking(move || {
        let pid_argument = pid.to_string();

        let _ = std::process::Command::new("taskkill")
            .args(["/PID", pid_argument.as_str(), "/T", "/F"])
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    })
    .await;
}

#[cfg(not(target_os = "windows"))]
async fn force_stop_sidecar_tree(_pid: u32) {}

pub async fn stop_sidecar(state: AppState) {
    // The desktop app owns this sidecar PID. On Windows, taskkill /T removes
    // the sidecar and any PyInstaller child processes beneath it.
    let child = {
        let mut runtime = state.runtime.lock().await;
        runtime.child.take()
    };

    if let Some(child) = child {
        force_stop_sidecar_tree(child.pid()).await;
    }

    state.stopped().await;
}

