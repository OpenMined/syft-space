use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

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

            // Spawn the Python backend sidecar
            let sidecar = app.shell().sidecar("syft-space").unwrap();
            let (mut rx, child) = sidecar.spawn().expect("failed to spawn sidecar");

            // Store the child process so we can kill it on exit
            app.manage(Mutex::new(Some(child)));

            // Log sidecar stdout/stderr
            tauri::async_runtime::spawn(async move {
                use tauri_plugin_shell::process::CommandEvent;
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            log::info!("[sidecar] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Stderr(line) => {
                            log::error!("[sidecar] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Terminated(status) => {
                            log::warn!("[sidecar] terminated with {:?}", status);
                            break;
                        }
                        _ => {}
                    }
                }
            });

            // Start periodic update checks
            updates::_start_periodic_update_checks(app.handle());

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                let state: tauri::State<Mutex<Option<tauri_plugin_shell::process::CommandChild>>> =
                    app.state();
                let mut guard = state.lock().unwrap();
                if let Some(child) = guard.take() {
                    let _ = child.kill();
                }
            }
        });
}
