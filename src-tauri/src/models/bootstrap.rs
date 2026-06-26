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
