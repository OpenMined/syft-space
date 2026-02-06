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
        .plugin(
            tauri_plugin_log::Builder::default()
                .clear_targets()
                .format(|out, message, record| {
                    let format = time_macros::format_description!(
                        "[[[year]-[month]-[day]][[[hour]:[minute]:[second]]"
                    );
                    let time_now = tauri_plugin_log::TimezoneStrategy::UseUtc
                        .get_now()
                        .format(&format)
                        .unwrap();
                    out.finish(format_args!(
                        "{}[{}][{}] {}",
                        time_now,
                        record.target(),
                        record.level(),
                        message
                    ))
                })
                .target(tauri_plugin_log::Target::new(
                    tauri_plugin_log::TargetKind::Stdout,
                ))
                .target(tauri_plugin_log::Target::new(
                    tauri_plugin_log::TargetKind::Folder {
                        path: dirs::home_dir()
                            .expect("Failed to get home directory")
                            .join(".syft-space")
                            .join("logs"),
                        file_name: Some("syft-space-desktop".to_string()),
                    },
                ))
                .level(log::LevelFilter::Info)
                .build(),
        )
        .setup(|app| {
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
                .sidecar("syft-space-backend")
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
                                .join(".syft-space")
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

            // Log syft-space-backend stdout/stderr to console and file
            let log_path = dirs::home_dir()
                .expect("Failed to get home directory")
                .join(".syft-space")
                .join("logs")
                .join("syft-space-backend.log");
            if let Some(parent) = log_path.parent() {
                std::fs::create_dir_all(parent).ok();
            }
            tauri::async_runtime::spawn(async move {
                use std::io::Write;
                use tauri_plugin_shell::process::CommandEvent;

                let mut log_file = std::fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(&log_path)
                    .expect("failed to open syft-space-backend log file");

                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            let msg = String::from_utf8_lossy(&line);
                            log::info!("[backend] {}", msg);
                            let _ = writeln!(log_file, "{}", msg);
                        }
                        CommandEvent::Stderr(line) => {
                            let msg = String::from_utf8_lossy(&line);
                            log::error!("[backend] {}", msg);
                            let _ = writeln!(log_file, "{}", msg);
                        }
                        CommandEvent::Terminated(status) => {
                            let msg = format!("terminated with {:?}", status);
                            log::warn!("[backend] {}", msg);
                            let _ = writeln!(log_file, "{}", msg);
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
