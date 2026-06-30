use serde::{Deserialize, Serialize};

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BootstrapStatus {
    pub sidecar_status: String,
    pub message: String,
    pub protocol_version: Option<String>,
}

// This model is received from the FastAPI sidecar through SidecarProxy.
// It therefore needs Deserialize as well as Serialize: Rust must be able to
// convert the JSON response body into this strongly typed struct.
#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GitInstallationStatus {
    pub status: String,
    pub version: Option<String>,
    pub message: String,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DiagnosticsStatus {
    pub app_version: String,
    pub environment: String,
    pub protocol_version: String,
    pub database_path: String,
    pub database_exists: bool,
    pub repository_count: i64,
    pub git_status: String,
    pub git_version: Option<String>,
    pub llm_provider: Option<String>,
    pub llm_model: Option<String>,
    pub llm_api_key_set: bool,
    pub api_key_storage: String,
    pub generated_at: String,
    #[serde(default)]
    pub recent_sidecar_messages: Vec<String>,
}
