use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Repository {
    pub id: String,
    pub display_name: String,
    pub path_label: String,
    pub current_branch: Option<String>,
    pub external_llm_allowed: bool,
    pub last_opened_at: String,
    pub last_remote_refresh_at: Option<String>,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FolderClassificationKind {
    ExistingRepository,
    NestedRepository,
    InitialisationRequired,
    UnsupportedRepository,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FolderClassification {
    pub kind: FolderClassificationKind,
    pub selected_path: String,
    pub repository_root: Option<String>,
    pub can_initialise: bool,
    pub message: Option<String>,
}

fn default_read_action_params() -> Value {
    Value::Object(Default::default())
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReadActionRequest {
    pub action: String,
    #[serde(default = "default_read_action_params")]
    pub params: Value,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RepositorySnapshot {
    pub repository_id: String,
    pub branch: Option<String>,
    pub head_commit: Option<String>,
    pub upstream_remote: Option<String>,
    pub upstream_branch: Option<String>,
    pub staged_changes: Vec<Value>,
    pub modified_changes: Vec<Value>,
    pub untracked_paths: Vec<Value>,
    pub conflicts: Vec<Value>,
    pub ahead: i64,
    pub behind: i64,
    pub remote_last_refreshed_at: Option<String>,
    pub write_blocked_reason: Option<String>,
    pub fingerprint: String,
    pub recent_commits: Vec<Value>,
    #[serde(default)]
    pub remote_names: Vec<String>,
    #[serde(default)]
    pub remote_urls: std::collections::HashMap<String, String>,
    #[serde(default)]
    pub local_branches: Vec<Value>,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReadActionResult {
    pub action: String,
    pub title: String,
    pub summary: String,
    pub content: String,
    #[serde(default)]
    pub content_kind: Option<String>,
    pub snapshot: RepositorySnapshot,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ActionPlanStep {
    pub kind: String,
    pub title: String,
    pub detail: String,
    #[serde(default)]
    pub paths: Vec<String>,
    pub commit_message: Option<String>,
    pub remote: Option<String>,
    pub branch: Option<String>,
    pub remote_url: Option<String>,
    pub stash_ref: Option<String>,
    pub command_preview: Option<String>,
    pub ahead: Option<i32>,
    pub behind: Option<i32>,
    pub force: Option<bool>,
    #[serde(default)]
    pub set_upstream: bool,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LocalActionPlan {
    pub matched: bool,
    pub repository_id: String,
    pub message: String,
    pub plan_kind: Option<String>,
    pub requires_confirmation: bool,
    pub plan_id: Option<String>,
    pub read_action: Option<String>,
    #[serde(default = "default_read_action_params")]
    pub read_params: Value,
    #[serde(default)]
    pub steps: Vec<ActionPlanStep>,
    pub explanation: String,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ActionExecutionResult {
    pub plan_id: String,
    pub title: String,
    pub summary: String,
    pub content: String,
    pub snapshot: RepositorySnapshot,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CancelActionPlanResponse {
    pub cancelled: bool,
}
