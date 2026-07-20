mod app_state;
mod commands;
mod models;
mod sidecar;
mod sidecar_proxy;

use std::sync::atomic::Ordering;
use tauri::RunEvent;

use app_state::AppState;
use sidecar_proxy::SidecarProxy;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let state = AppState::default();
    let proxy = SidecarProxy::new().expect("Unable to initialise the local sidecar proxy.");
    let startup_state = state.clone();
    let shutdown_state = state.clone();

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(state.clone())
        .manage(proxy.clone())
        .setup(move |app| {
            sidecar::launch(app.handle().clone(), startup_state.clone());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::bootstrap::get_bootstrap_status,
            commands::bootstrap::get_git_installation_status,
            commands::bootstrap::get_diagnostics_status,
            commands::repositories::list_repositories,
            commands::repositories::pick_and_classify_repository,
            commands::repositories::register_repository,
            commands::repositories::initialise_and_register_repository,
            commands::repositories::get_repository_snapshot,
            commands::repositories::list_agent_sessions,
            commands::repositories::create_agent_session,
            commands::repositories::compare_agent_session,
            commands::repositories::merge_agent_session,
            commands::repositories::abandon_agent_session,
            commands::repositories::cleanup_agent_session,
            commands::repositories::run_read_action,
            commands::repositories::preview_conflict_resolution,
            commands::repositories::apply_conflict_resolution,
            commands::repositories::resolve_local_request,
            commands::repositories::execute_action_plan,
            commands::repositories::cancel_action_plan,
            commands::repositories::submit_action_plan,
            commands::repositories::generate_commit_message,
            commands::repositories::generate_change_summary,
            commands::repositories::generate_pull_request_draft,
            commands::repositories::add_to_gitignore,
            commands::repositories::remove_repository,
            commands::repositories::pick_clone_target,
            commands::repositories::pick_release_asset,
            commands::repositories::clone_repository,
            commands::repositories::draft_github_release,
            commands::repositories::get_github_draft_release,
            commands::repositories::publish_github_repository,
            commands::repositories::draft_github_pull_request,
            commands::repositories::draft_gitlab_merge_request,
            commands::settings::get_llm_settings,
            commands::settings::update_llm_settings,
            commands::settings::get_github_settings,
            commands::settings::update_github_settings,
            commands::settings::get_gitlab_settings,
            commands::settings::update_gitlab_settings,
            commands::settings::get_git_identity_settings,
            commands::settings::update_git_identity_settings,
            commands::settings::test_llm_connection,
            commands::settings::set_repository_llm_allowed,
        ])
        .build(tauri::generate_context!())
        .expect("error while building AI Git Assistant");

    app.run(move |app_handle, event| {
        if let RunEvent::ExitRequested { api, .. } = event {
            // The first exit request is the user closing the application. Pause it
            // while Rust terminates the private sidecar process tree.
            if shutdown_state
                .shutdown_started
                .swap(true, Ordering::AcqRel)
            {
                // app_handle.exit(0) triggers a second ExitRequested event after
                // cleanup. Let that final event exit normally.
                return;
            }

            api.prevent_exit();

            let state = shutdown_state.clone();
            let app_handle = app_handle.clone();

            tauri::async_runtime::spawn(async move {
                sidecar::stop_sidecar(state).await;

                // Cleanup is complete, so allow Tauri to perform its normal exit.
                app_handle.exit(0);
            });
        }
    });
}
