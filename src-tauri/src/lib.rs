use std::sync::Mutex;
use tauri::Manager;

mod commands;
mod state;
mod updates;
mod windows;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            commands::update_window_response,
            commands::get_window_state,
        ])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Initialize state
            app.manage(Mutex::new(state::AppState::default()));
            app.manage(state::PendingUpdate {
                pending_update: Mutex::new(None),
                pending_update_window_state: Mutex::new(None),
            });

            // Start periodic update checks
            updates::_start_periodic_update_checks(app.handle());

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
