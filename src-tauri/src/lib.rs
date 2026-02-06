use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

mod commands;
mod state;
mod updates;
mod utils;
mod windows;

fn find_child_process_pids() -> Vec<String> {
    use sysinfo::System;

    let mut sys = System::new_all();
    sys.refresh_all();
    let current_pid = sysinfo::Pid::from_u32(std::process::id());
    let mut child_process_pids = Vec::new();
    for (pid, process) in sys.processes() {
        if let Some(parent_pid) = process.parent() {
            if parent_pid == current_pid {
                child_process_pids.push(pid.to_string());
            }
        }
    }
    child_process_pids
}

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

            // Generate server connection args (host, port, auth token)
            let (host, port, token) = utils::generate_server_args();
            log::info!("Server args - host: {}, port: {}", host, port);

            // Spawn the Python backend sidecar with connection params
            let sidecar = app
                .shell()
                .sidecar("syft-space")
                .unwrap()
                .env("SYFT_HOST", &host)
                .env("SYFT_PORT", &port)
                .env("SYFT_ADMIN_API_KEY", &token);
            let (mut rx, _child) = sidecar.spawn().expect("failed to spawn sidecar");

            // Create main window with connection params in URL
            let url = utils::generate_main_url(&host, &port, &token);
            windows::_setup_main_window(app.handle(), url);

            let main_process_pid = std::process::id();
            let child_process_pids = find_child_process_pids();

            let app_handle = app.app_handle().clone();
            tauri::async_runtime::spawn(async move {
                loop {
                    log::info!("Starting process-wick sidecar");
                    let exit_code = app_handle
                        .shell()
                        .sidecar("process-wick")
                        .unwrap()
                        .args([
                            "--dog",
                            &main_process_pid.to_string(),
                            "--targets",
                            &child_process_pids.join(","),
                            "--log-file",
                            dirs::home_dir()
                                .expect("Failed to get home directory")
                                .join(".syftbox")
                                .join("logs")
                                .join("syft-space-process-wick.log")
                                .to_str()
                                .unwrap(),
                        ])
                        .status()
                        .await
                        .unwrap()
                        .code()
                        .unwrap_or_else(|| {
                            log::warn!("process-wick sidecar exited without a status code");
                            1
                        });

                    log::warn!(
                        "process-wick sidecar exited with status: {:?}, restarting...",
                        exit_code
                    );

                    // Small delay before restarting to avoid rapid restart loops
                    std::thread::sleep(std::time::Duration::from_secs(1));
                }
            });

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
        .run(|_app, _event| {});
}
