//! Application state and data structures

use serde::Serialize;
use std::sync::Mutex;
use tauri_plugin_updater::Update;

#[derive(Default)]
pub struct AppState {
    pub prevent_auto_update_check_for_version: String,
}

/// Immutable backend connection params (set once during setup)
pub struct BackendConnection {
    pub host: String,
    pub port: String,
    pub token: String,
}

/// Mutable tray status (updated by polling loop)
#[derive(Default, Clone, PartialEq)]
pub struct TrayState {
    pub server_running: bool,
    pub tunnel_connected: bool,
    pub tunnel_has_token: bool,
    pub tunnel_url: Option<String>,
    pub endpoint_count: usize,
}

pub struct PendingUpdate {
    pub pending_update: Mutex<Option<Update>>,
    pub pending_update_window_state: Mutex<Option<UpdateWindowState>>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum UpdateWindowType {
    Checking,
    None,
    Available,
    Downloading,
    Error,
    Failed,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateWindowState {
    pub update_window_type: UpdateWindowType,
    pub version: String,
    pub current_version: String,
    pub release_notes: String,
    pub error: String,
    pub progress: usize,
}
