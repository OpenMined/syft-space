use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

mod commands;
mod state;
mod tray;
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

/// Resolve the path to the syft-space-backend executable.
/// In debug builds, SYFT_BACKEND_PATH env var can override the path.
fn resolve_backend_path(app: &tauri::App) -> std::path::PathBuf {
    if cfg!(debug_assertions) {
        if let Ok(override_path) = std::env::var("SYFT_BACKEND_PATH") {
            return std::path::PathBuf::from(override_path);
        }
    }

    let exe_name = if cfg!(windows) {
        "syft-space-backend.exe"
    } else {
        "syft-space-backend"
    };

    app.path()
        .resource_dir()
        .expect("failed to resolve resource directory")
        .join("syft-space-backend")
        .join(exe_name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .invoke_handler(tauri::generate_handler![
            commands::update_window_response,
            commands::get_window_state,
            commands::reset_tcc_permission,
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

            // Store backend connection info for tray polling
            app.manage(state::BackendConnection {
                host: host.clone(),
                port: port.clone(),
                token: token.clone(),
            });
            app.manage(Mutex::new(state::TrayState::default()));

            // Resolve the backend executable path from resources
            let backend_path = resolve_backend_path(app);
            log::info!("Backend path: {:?}", backend_path);

            // Ensure the backend binary is executable on Unix
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                if let Ok(metadata) = std::fs::metadata(&backend_path) {
                    let mut perms = metadata.permissions();
                    let mode = perms.mode();
                    if mode & 0o111 == 0 {
                        perms.set_mode(mode | 0o755);
                        let _ = std::fs::set_permissions(&backend_path, perms);
                    }
                }
            }

            // Spawn the Python backend using std::process::Command
            let mut child = std::process::Command::new(&backend_path)
                .env("SYFT_HOST", &host)
                .env("SYFT_PORT", &port)
                .env("SYFT_ADMIN_API_KEY", &token)
                .stdout(std::process::Stdio::piped())
                .stderr(std::process::Stdio::piped())
                .spawn()
                .expect("failed to spawn backend process");

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

            // Spawn stdout reader thread
            let stdout = child.stdout.take().expect("failed to take stdout");
            let stdout_log_path = log_path.clone();
            std::thread::spawn(move || {
                use std::io::{BufRead, BufReader, Write};

                let mut log_file = std::fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(&stdout_log_path)
                    .expect("failed to open syft-space-backend log file");

                let reader = BufReader::new(stdout);
                for line in reader.lines() {
                    match line {
                        Ok(line) => {
                            log::info!("[backend] {}", line);
                            let _ = writeln!(log_file, "{}", line);
                        }
                        Err(_) => break,
                    }
                }
            });

            // Spawn stderr reader thread
            let stderr = child.stderr.take().expect("failed to take stderr");
            let stderr_log_path = log_path.clone();
            std::thread::spawn(move || {
                use std::io::{BufRead, BufReader, Write};

                let mut log_file = std::fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(&stderr_log_path)
                    .expect("failed to open syft-space-backend log file");

                let reader = BufReader::new(stderr);
                for line in reader.lines() {
                    match line {
                        Ok(line) => {
                            log::error!("[backend] {}", line);
                            let _ = writeln!(log_file, "{}", line);
                        }
                        Err(_) => break,
                    }
                }
            });

            // Spawn thread to wait for the backend process to exit and log the status
            std::thread::spawn(move || match child.wait() {
                Ok(status) => {
                    log::warn!("[backend] terminated with status: {:?}", status);
                }
                Err(e) => {
                    log::error!("[backend] error waiting for process: {:?}", e);
                }
            });

            // Start periodic update checks
            updates::_start_periodic_update_checks(app.handle());

            // Set up system tray
            tray::setup_tray(app.handle())?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() == "main" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    // Hide the window instead of closing it
                    api.prevent_close();
                    let _ = window.hide();

                    #[cfg(target_os = "macos")]
                    {
                        let app = window.app_handle();
                        let _ = app.set_activation_policy(tauri::ActivationPolicy::Accessory);
                    }
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            #[cfg(target_os = "macos")]
            if let tauri::RunEvent::Reopen { .. } = event {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                    let _ = app.set_activation_policy(tauri::ActivationPolicy::Regular);
                }
            }
            // Suppress unused variable warnings on non-macOS
            #[cfg(not(target_os = "macos"))]
            {
                let _ = (app, event);
            }
        });
}
