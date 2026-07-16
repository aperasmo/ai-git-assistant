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
#[serde(rename_all = "camelCase")]
pub struct CreateAgentSessionRequest {
    pub task: String,
    pub branch_name: Option<String>,
    pub base_branch: Option<String>,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentSession {
    pub id: String,
    pub repository_id: String,
    pub task: String,
    pub branch_name: String,
    pub base_branch: String,
    pub worktree_path: String,
    pub status: String,
    pub changed_file_count: i64,
    pub commits_ahead: i64,
    pub last_commit: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentSessionComparisonResponse {
    pub session: AgentSession,
    pub title: String,
    pub summary: String,
    pub content: String,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentSessionActionResponse {
    pub session: AgentSession,
    pub title: String,
    pub summary: String,
    pub content: String,
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

fn default_commit_style() -> String {
    "detailed".to_string()
}

fn default_commit_confidence() -> String {
    "medium".to_string()
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
pub struct RemoteProviderInfo {
    pub remote: String,
    pub provider: String,
    pub label: String,
    pub host: Option<String>,
    pub url: Option<String>,
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
    pub remote_providers: Vec<RemoteProviderInfo>,
    #[serde(default)]
    pub local_branches: Vec<Value>,
    #[serde(default)]
    pub local_tags: Vec<String>,
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
    pub tag_name: Option<String>,
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
    #[serde(default)]
    pub source: Option<String>,
    #[serde(default)]
    pub risk: Option<Value>,
    #[serde(default)]
    pub privacy_receipt: Option<Value>,
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
pub struct GenerateCommitMessageResponse {
    pub message: String,
    #[serde(default)]
    pub subject: String,
    #[serde(default)]
    pub body: Vec<String>,
    #[serde(default)]
    pub warning: Option<String>,
    #[serde(default = "default_commit_style")]
    pub style: String,
    #[serde(default = "default_commit_confidence")]
    pub confidence: String,
    #[serde(default)]
    pub detected_scope: Vec<String>,
    #[serde(default)]
    pub alternatives: Vec<String>,
    pub source: String,
    pub context_summary: String,
    #[serde(default)]
    pub privacy_receipt: Option<Value>,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GenerateChangeSummaryResponse {
    pub branch_summary: String,
    #[serde(default)]
    pub file_summaries: Vec<String>,
    pub pr_title: String,
    pub pr_body: String,
    #[serde(default)]
    pub commit_suggestions: Vec<Value>,
    pub source: String,
    pub context_summary: String,
    #[serde(default)]
    pub privacy_receipt: Option<Value>,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GeneratePullRequestDraftResponse {
    pub title: String,
    pub body: String,
    #[serde(default)]
    pub checklist: Vec<String>,
    pub branch_summary: String,
    #[serde(default)]
    pub file_summaries: Vec<String>,
    pub source: String,
    pub context_summary: String,
    #[serde(default)]
    pub privacy_receipt: Option<Value>,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DraftGitHubReleaseRequest {
    pub tag_name: String,
    pub title: String,
    pub body: String,
    pub asset_path: Option<String>,
    #[serde(default)]
    pub asset_paths: Vec<String>,
    pub prerelease: bool,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReleaseAssetUpload {
    pub name: String,
    pub url: Option<String>,
    pub sha256: Option<String>,
    #[serde(default)]
    pub status: String,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DraftGitHubReleaseResponse {
    pub tag_name: String,
    pub repository: String,
    pub release_url: String,
    #[serde(default)]
    pub action: String,
    pub asset_url: Option<String>,
    pub asset_name: Option<String>,
    pub asset_sha256: Option<String>,
    #[serde(default)]
    pub assets: Vec<ReleaseAssetUpload>,
    pub title: String,
    pub summary: String,
    pub content: String,
    pub snapshot: RepositorySnapshot,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DraftGitHubPullRequestRequest {
    pub base_branch: String,
    pub title: String,
    pub body: String,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DraftGitHubPullRequestResponse {
    pub repository: String,
    pub pull_request_url: String,
    pub number: i64,
    pub base_branch: String,
    pub head_branch: String,
    pub provider: String,
    pub title: String,
    pub summary: String,
    pub content: String,
    pub snapshot: RepositorySnapshot,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DraftGitLabMergeRequestRequest {
    pub base_branch: String,
    pub title: String,
    pub body: String,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DraftGitLabMergeRequestResponse {
    pub repository: String,
    pub merge_request_url: String,
    pub number: i64,
    pub base_branch: String,
    pub head_branch: String,
    pub provider: String,
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
