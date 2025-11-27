//! Tauri command handlers

use crate::state::{AppState, PendingUpdate, UpdateWindowState, UpdateWindowType};
use crate::windows::_show_update_window;
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Manager};

#[tauri::command]
pub async fn update_window_response(app: AppHandle, install_update: bool) -> Result<(), String> {
    log::info!(
        "Update window response received - install: {}",
        install_update
    );
    let pending_update_state = app.state::<PendingUpdate>();
    let update_opt = {
        let guard = pending_update_state.pending_update.lock().unwrap();
        guard.clone()
    };

    if let Some(update) = update_opt {
        if install_update {
            log::info!(
                "Starting update installation for version {}",
                update.version
            );
            let mut downloaded_chunks: u64 = 0;
            let mut last_shown_percent: i32 = -1; // Track last shown percentage

            let app_clone_for_progress = app.clone();
            let update_version = Arc::new(update.version.clone());
            let current_version = Arc::new(update.current_version.clone());

            if let Err(e) = update
                .download_and_install(
                    {
                        let update_version = Arc::clone(&update_version);
                        let current_version = Arc::clone(&current_version);
                        move |chunk_length, content_length| {
                            downloaded_chunks += chunk_length as u64;
                            let percent = (downloaded_chunks as f64
                                / content_length.unwrap_or(downloaded_chunks) as f64)
                                * 100.0;

                            let current_percent = percent as i32;

                            if current_percent > last_shown_percent {
                                log::debug!("Update download progress: {:.1}%", percent);
                                _show_update_window(
                                    &app_clone_for_progress,
                                    UpdateWindowType::Downloading,
                                    update_version.to_string(),
                                    current_version.to_string(),
                                    "".to_string(),
                                    "".to_string(),
                                    current_percent as usize,
                                );
                                last_shown_percent = current_percent;
                            }
                        }
                    },
                    || {},
                )
                .await
            {
                log::error!("Failed to download and install update: {}", e);
                let error_message = format!(
                    "Failed to download and install update.\nPlease try again later.\n\nError: {}",
                    e
                );
                _show_update_window(
                    &app,
                    UpdateWindowType::Failed,
                    update_version.to_string(),
                    current_version.to_string(),
                    "".to_string(),
                    error_message,
                    0,
                );
            } else {
                log::info!("Update installation complete - restarting application");
                app.restart();
            }
        } else {
            log::info!("User declined update for version {}", update.version);
            let app_state_data = app.state::<Mutex<AppState>>();
            let mut guard = app_state_data.lock().unwrap();
            guard.prevent_auto_update_check_for_version = update.version.clone();
        }
    }
    Ok(())
}

#[tauri::command]
pub fn get_window_state(app: AppHandle) -> UpdateWindowState {
    let pending_update_state = app.state::<PendingUpdate>();
    let guard = pending_update_state
        .pending_update_window_state
        .lock()
        .unwrap();

    guard.clone().unwrap_or(UpdateWindowState {
        update_window_type: UpdateWindowType::Checking,
        version: "".to_string(),
        current_version: app.package_info().version.to_string(),
        release_notes: "".to_string(),
        error: "".to_string(),
        progress: 0,
    })
}
