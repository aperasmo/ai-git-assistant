use reqwest::{Client, Method};
use serde::de::DeserializeOwned;
use serde::Serialize;

use crate::app_state::AppState;

#[derive(Clone)]
pub struct SidecarProxy {
    client: Client,
}

impl SidecarProxy {
    pub fn new() -> Result<Self, String> {
        // The Rust layer owns this HTTP client. React never receives either
        // the sidecar endpoint or the per-session token used below.
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(90))
            .build()
            .map_err(|error| format!("Unable to create local HTTP client: {error}"))?;
        Ok(Self { client })
    }

    async fn details(state: &AppState) -> Result<(String, String), String> {
        let runtime = state.runtime.lock().await;
        match (&runtime.endpoint, &runtime.session_token) {
            (Some(endpoint), Some(token)) => Ok((endpoint.clone(), token.clone())),
            _ => Err("The local service is not ready.".to_owned()),
        }
    }

    pub async fn get<T: DeserializeOwned>(
        &self,
        state: &AppState,
        path: &str,
    ) -> Result<T, String> {
        self.request::<(), T>(state, Method::GET, path, None).await
    }

    pub async fn post<Req: Serialize + ?Sized, Res: DeserializeOwned>(
        &self,
        state: &AppState,
        path: &str,
        payload: &Req,
    ) -> Result<Res, String> {
        self.request(state, Method::POST, path, Some(payload)).await
    }

    pub async fn delete(&self, state: &AppState, path: &str) -> Result<(), String> {
        let (endpoint, token) = Self::details(state).await?;
        let url = format!("{endpoint}{path}");
        let response = self
            .client
            .request(Method::DELETE, url)
            .bearer_auth(token)
            .header("Content-Type", "application/json")
            .send()
            .await
            .map_err(|error| format!("The local service could not be reached: {error}"))?;

        if !response.status().is_success() {
            let body = response.text().await.unwrap_or_default();
            let detail = serde_json::from_str::<serde_json::Value>(&body)
                .ok()
                .and_then(|json| json.get("detail").cloned())
                .map(|d| match d {
                    serde_json::Value::String(m) => m,
                    other => other.to_string(),
                })
                .unwrap_or_else(|| "The local service rejected the request.".to_owned());
            return Err(detail);
        }
        Ok(())
    }

    pub async fn put<Req: Serialize + ?Sized, Res: DeserializeOwned>(
        &self,
        state: &AppState,
        path: &str,
        payload: &Req,
    ) -> Result<Res, String> {
        self.request(state, Method::PUT, path, Some(payload)).await
    }

    async fn request<Req: Serialize + ?Sized, Res: DeserializeOwned>(
        &self,
        state: &AppState,
        method: Method,
        path: &str,
        payload: Option<&Req>,
    ) -> Result<Res, String> {
        let (endpoint, token) = Self::details(state).await?;
        let url = format!("{endpoint}{path}");

        // The bearer token is attached inside Rust only. The webview cannot
        // create arbitrary sidecar requests or read this token from state.
        let mut request = self
            .client
            .request(method, url)
            .bearer_auth(token)
            .header("Content-Type", "application/json");

        if let Some(body) = payload {
            request = request.json(body);
        }

        let response = request
            .send()
            .await
            .map_err(|error| format!("The local service could not be reached: {error}"))?;

        if !response.status().is_success() {
            let body = response.text().await.unwrap_or_default();
            let detail = serde_json::from_str::<serde_json::Value>(&body)
                .ok()
                .and_then(|json| json.get("detail").cloned())
                .map(|detail| match detail {
                    serde_json::Value::String(message) => message,
                    other => other.to_string(),
                })
                .unwrap_or_else(|| "The local service rejected the request.".to_owned());
            return Err(detail);
        }

        response
            .json::<Res>()
            .await
            .map_err(|error| format!("The local service returned an invalid response: {error}"))
    }
}
