//! Update-related functionality

use crate::state::{AppState, PendingUpdate, UpdateWindowType};
use crate::windows::_show_update_window;
use std::{sync::Mutex, thread, time::Duration};
use tauri::{AppHandle, Manager};
use tauri_plugin_updater::UpdaterExt;

pub fn _start_periodic_update_checks(app: &AppHandle) {
    log::info!("Starting periodic update checks");
    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        loop {
            _check_for_updates(&app_handle, false).await;
            thread::sleep(Duration::from_secs(3600)); // Sleep for 1 hour
        }
    });
}

pub async fn _check_for_updates(app: &AppHandle, has_user_checked_manually: bool) {
    log::info!(
        "Checking for updates (manual check: {})",
        has_user_checked_manually
    );
    let handle = app.clone();
    let current_version = handle.package_info().version.to_string();

    if has_user_checked_manually {
        _show_update_window(
            app,
            UpdateWindowType::Checking,
            "".to_string(),
            current_version.clone(),
            "".to_string(),
            "".to_string(),
            0,
        );
    }
    let update_result = handle.updater().unwrap().check().await;
    match update_result {
        Ok(Some(update)) => {
            log::info!(
                "Update available: {} (current: {})",
                update.version,
                update.current_version
            );
            let app_state_mutex = app.state::<Mutex<AppState>>();
            let should_check_for_update = {
                let state_guard = app_state_mutex.lock().unwrap();
                has_user_checked_manually
                    || state_guard.prevent_auto_update_check_for_version != update.version
            };
            if !should_check_for_update {
                log::debug!(
                    "Skipping update check as it was already shown for version {}",
                    update.version
                );
                return;
            }

            _show_update_window(
                app,
                UpdateWindowType::Available,
                update.version.clone(),
                update.current_version.clone(),
                update
                    .body
                    .clone()
                    .unwrap_or_else(|| "No release notes available".to_string()),
                "".to_string(),
                0,
            );

            let pending_update_state = app.state::<PendingUpdate>();
            // The actual `Update` struct comes from `tauri_plugin_updater::Update`
            // This assignment should be fine as `pending_update_state.pending_update` is `Mutex<Option<tauri_plugin_updater::Update>>`
            *pending_update_state.pending_update.lock().unwrap() = Some(update);
        }
        Ok(None) => {
            log::info!("No updates available");
            if has_user_checked_manually {
                _show_update_window(
                    app,
                    UpdateWindowType::None,
                    "".to_string(),
                    current_version.clone(),
                    "".to_string(),
                    "".to_string(),
                    0,
                );
            }
        }
        Err(e) => {
            log::error!("Failed to check for updates: {}", e);
            if has_user_checked_manually {
                let error_message = format!(
                    "Failed to check for updates.\nPlease try again later.\n\nError: {}",
                    e
                );
                _show_update_window(
                    app,
                    UpdateWindowType::Error,
                    "".to_string(),
                    current_version.clone(),
                    "".to_string(),
                    error_message,
                    0,
                );
            }
        }
    }
}
