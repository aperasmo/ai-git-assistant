use std::{io::ErrorKind, process::Command};

use serde::{Deserialize, Serialize};
use tauri::State;

use crate::{
    app_state::AppState,
    models::{
        repositories::Repository,
        settings::{
            GitHubSettings, GitIdentitySettings, GitLabSettings, LLMSettings,
            SetExternalLLMRequest, UpdateGitHubSettingsRequest, UpdateGitIdentityRequest,
            UpdateGitLabSettingsRequest, UpdateLLMSettingsRequest,
        },
    },
    sidecar_proxy::SidecarProxy,
};

#[derive(Debug, Serialize, Deserialize)]
pub struct LLMTestResult {
    pub ok: bool,
    pub message: String,
}

fn run_git_config(args: &[&str]) -> Result<(bool, String, String), String> {
    let output = Command::new("git")
        .arg("config")
        .args(args)
        .output()
        .map_err(|err| {
            if err.kind() == ErrorKind::NotFound {
                "Git is not available on PATH.".to_string()
            } else {
                format!("Unable to run git config: {err}")
            }
        })?;

    Ok((
        output.status.success(),
        String::from_utf8_lossy(&output.stdout).trim().to_string(),
        String::from_utf8_lossy(&output.stderr).trim().to_string(),
    ))
}

fn get_global_git_config_value(key: &str) -> Result<Option<String>, String> {
    let (ok, stdout, stderr) = run_git_config(&["--global", "--get", key])?;
    if ok && !stdout.is_empty() {
        return Ok(Some(stdout));
    }
    if !ok && !stderr.is_empty() && !stderr.contains("key does not contain") {
        return Err(stderr);
    }
    Ok(None)
}

fn build_git_identity_response(
    user_name: Option<String>,
    user_email: Option<String>,
    git_available: bool,
) -> GitIdentitySettings {
    let configured = user_name
        .as_deref()
        .is_some_and(|value| !value.trim().is_empty())
        && user_email
            .as_deref()
            .is_some_and(|value| !value.trim().is_empty());
    let message = if !git_available {
        "Git is not available on PATH.".to_string()
    } else if configured {
        "Git commits will use this global author identity.".to_string()
    } else {
        "Set your name and email before committing from this machine.".to_string()
    };

    GitIdentitySettings {
        user_name,
        user_email,
        configured,
        git_available,
        message,
    }
}

#[tauri::command(rename_all = "camelCase")]
pub async fn get_git_identity_settings() -> Result<GitIdentitySettings, String> {
    match (
        get_global_git_config_value("user.name"),
        get_global_git_config_value("user.email"),
    ) {
        (Ok(user_name), Ok(user_email)) => {
            Ok(build_git_identity_response(user_name, user_email, true))
        }
        (Err(message), _) | (_, Err(message)) if message == "Git is not available on PATH." => {
            Ok(build_git_identity_response(None, None, false))
        }
        (Err(message), _) | (_, Err(message)) => Err(message),
    }
}

#[tauri::command(rename_all = "camelCase")]
pub async fn update_git_identity_settings(
    request: UpdateGitIdentityRequest,
) -> Result<GitIdentitySettings, String> {
    let user_name = request.user_name.unwrap_or_default().trim().to_string();
    let user_email = request.user_email.unwrap_or_default().trim().to_string();

    if user_name.is_empty() || user_email.is_empty() {
        return Err("Enter both a Git author name and email.".to_string());
    }

    for (key, value) in [("user.name", user_name.as_str()), ("user.email", user_email.as_str())] {
        let (ok, _stdout, stderr) = run_git_config(&["--global", key, value])?;
        if !ok {
            return Err(if stderr.is_empty() {
                format!("Unable to save Git config value for {key}.")
            } else {
                stderr
            });
        }
    }

    Ok(build_git_identity_response(
        Some(user_name),
        Some(user_email),
        true,
    ))
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
