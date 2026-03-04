//! System tray menu setup, event handling, and status polling

use crate::state::{BackendConnection, TrayState};
use crate::updates::_check_for_updates;
use crate::windows::_show_about_window;
use std::sync::Mutex;
use tauri::menu::{CheckMenuItem, IsMenuItem, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Manager};

const TRAY_ID: &str = "main-tray";

// Menu item IDs
const ID_OPEN: &str = "open";
const ID_STATUS_SERVER: &str = "status_server";
const ID_STATUS_TUNNEL: &str = "status_tunnel";
const ID_STATUS_ENDPOINTS: &str = "status_endpoints";
const ID_RESTART: &str = "restart";
const ID_COPY_URL: &str = "copy_url";
const ID_AUTOSTART: &str = "autostart";
const ID_CHECK_UPDATES: &str = "check_updates";
const ID_ABOUT: &str = "about";
const ID_QUIT: &str = "quit";

/// Build the tray menu from current state.
fn build_menu(app: &AppHandle, state: &TrayState) -> tauri::Result<tauri::menu::Menu<tauri::Wry>> {
    // "Open Syft Space"
    let open_item = MenuItem::with_id(app, ID_OPEN, "Open Syft Space", true, None::<&str>)?;

    let sep1 = PredefinedMenuItem::separator(app)?;

    // Status items (disabled, display-only)
    let server_text = if state.server_running {
        "Server: Running \u{2713}"
    } else {
        "Server: Stopped"
    };
    let server_item = MenuItem::with_id(app, ID_STATUS_SERVER, server_text, false, None::<&str>)?;

    let tunnel_text = if state.tunnel_connected {
        "Tunnel: Connected \u{2713}"
    } else if state.tunnel_has_token {
        "Tunnel: Disconnected"
    } else {
        "Tunnel: Not Configured"
    };
    let tunnel_item = MenuItem::with_id(app, ID_STATUS_TUNNEL, tunnel_text, false, None::<&str>)?;

    let endpoints_text = format!("Endpoints: {} published", state.endpoint_count);
    let endpoints_item =
        MenuItem::with_id(app, ID_STATUS_ENDPOINTS, &endpoints_text, false, None::<&str>)?;

    let sep2 = PredefinedMenuItem::separator(app)?;

    // Action items
    let restart_item = MenuItem::with_id(app, ID_RESTART, "Restart Server", true, None::<&str>)?;

    let copy_url_enabled = state.tunnel_connected && state.tunnel_url.is_some();
    let copy_url_item = MenuItem::with_id(
        app,
        ID_COPY_URL,
        "Copy Public URL",
        copy_url_enabled,
        None::<&str>,
    )?;

    let sep3 = PredefinedMenuItem::separator(app)?;

    // Autostart checkbox
    let autostart_enabled = is_autostart_enabled(app);
    let autostart_item = CheckMenuItem::with_id(
        app,
        ID_AUTOSTART,
        "Autostart",
        true,
        autostart_enabled,
        None::<&str>,
    )?;

    let check_updates_item =
        MenuItem::with_id(app, ID_CHECK_UPDATES, "Check for Updates", true, None::<&str>)?;
    let about_item =
        MenuItem::with_id(app, ID_ABOUT, "About Syft Space", true, None::<&str>)?;
    let quit_item = MenuItem::with_id(app, ID_QUIT, "Quit", true, None::<&str>)?;

    let items: Vec<&dyn IsMenuItem<tauri::Wry>> = vec![
        &open_item,
        &sep1,
        &server_item,
        &tunnel_item,
        &endpoints_item,
        &sep2,
        &restart_item,
        &copy_url_item,
        &sep3,
        &autostart_item,
        &check_updates_item,
        &about_item,
        &quit_item,
    ];

    tauri::menu::Menu::with_items(app, &items)
}

/// Set up the system tray icon, menu, and event handler. Starts the status polling loop.
pub fn setup_tray(app: &AppHandle) -> tauri::Result<()> {
    let tray_state = app.state::<Mutex<TrayState>>();
    let initial_state = tray_state.lock().unwrap().clone();

    let menu = build_menu(app, &initial_state)?;

    let mut builder = TrayIconBuilder::with_id(TRAY_ID);

    #[cfg(target_os = "macos")]
    {
        let icon_bytes = include_bytes!("../icons/tray.png");
        let icon = tauri::image::Image::from_bytes(icon_bytes)?;
        builder = builder.icon(icon).icon_as_template(true);
    }

    #[cfg(not(target_os = "macos"))]
    {
        if let Some(icon) = app.default_window_icon() {
            builder = builder.icon(icon.clone());
        }
    }

    builder
        .menu(&menu)
        .tooltip("Syft Space")
        .on_menu_event(move |app, event| {
            handle_menu_event(app, event.id().as_ref());
        })
        .build(app)?;

    start_status_polling(app);

    Ok(())
}

/// Handle menu item click events.
fn handle_menu_event(app: &AppHandle, id: &str) {
    match id {
        ID_OPEN => {
            show_main_window(app);
        }
        ID_RESTART => {
            log::info!("Tray: restarting application");
            app.restart();
        }
        ID_COPY_URL => {
            let tray_state = app.state::<Mutex<TrayState>>();
            let url = tray_state.lock().unwrap().tunnel_url.clone();
            if let Some(url) = url {
                match arboard::Clipboard::new() {
                    Ok(mut clipboard) => {
                        if let Err(e) = clipboard.set_text(&url) {
                            log::error!("Failed to copy URL to clipboard: {}", e);
                        } else {
                            log::info!("Copied public URL to clipboard: {}", url);
                        }
                    }
                    Err(e) => {
                        log::error!("Failed to access clipboard: {}", e);
                    }
                }
            }
        }
        ID_AUTOSTART => {
            toggle_autostart(app);
        }
        ID_CHECK_UPDATES => {
            let app_handle = app.clone();
            tauri::async_runtime::spawn(async move {
                _check_for_updates(&app_handle, true).await;
            });
        }
        ID_ABOUT => {
            _show_about_window(app);
        }
        ID_QUIT => {
            log::info!("Tray: quitting application");
            app.exit(0);
        }
        _ => {
            log::debug!("Tray: unhandled menu event: {}", id);
        }
    }
}

/// Show (and focus) the main window, adjusting macOS activation policy.
fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        if let Err(e) = window.set_skip_taskbar(false) {
            log::error!("Failed to restore taskbar: {}", e);
        }
        if let Err(e) = window.show() {
            log::error!("Failed to show window: {}", e);
        }
        if let Err(e) = window.unminimize() {
            log::error!("Failed to unminimize window: {}", e);
        }
        if let Err(e) = window.set_focus() {
            log::error!("Failed to focus window: {}", e);
        }

        #[cfg(target_os = "macos")]
        {
            if let Err(e) = app.set_activation_policy(tauri::ActivationPolicy::Regular) {
                log::error!("Failed to set activation policy: {}", e);
            }
        }
    }
}

/// Start a polling loop that checks backend status every 5 seconds and rebuilds the menu when state changes.
fn start_status_polling(app: &AppHandle) {
    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        // Give the backend time to start
        std::thread::sleep(std::time::Duration::from_secs(3));

        loop {
            let new_state = poll_backend(&app_handle).await;

            let should_rebuild = {
                let tray_state = app_handle.state::<Mutex<TrayState>>();
                let mut current = tray_state.lock().unwrap();
                if *current != new_state {
                    *current = new_state.clone();
                    true
                } else {
                    false
                }
            };

            if should_rebuild {
                if let Some(tray) = app_handle.tray_by_id(TRAY_ID) {
                    match build_menu(&app_handle, &new_state) {
                        Ok(menu) => {
                            if let Err(e) = tray.set_menu(Some(menu)) {
                                log::error!("Failed to update tray menu: {}", e);
                            }
                        }
                        Err(e) => {
                            log::error!("Failed to build tray menu: {}", e);
                        }
                    }
                }
            }

            std::thread::sleep(std::time::Duration::from_secs(5));
        }
    });
}

/// Poll the backend for current status.
async fn poll_backend(app: &AppHandle) -> TrayState {
    let conn = app.state::<BackendConnection>();
    let base_url = format!("http://{}:{}", conn.host, conn.port);
    let token = conn.token.clone();

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(3))
        .build()
        .unwrap_or_default();

    let mut state = TrayState::default();

    // Check server health
    let health_url = format!("{}/api/v1/health", base_url);
    if let Ok(resp) = client
        .get(&health_url)
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
    {
        state.server_running = resp.status().is_success();
    }

    if !state.server_running {
        return state;
    }

    // Check tunnel/proxy status
    let proxy_url = format!("{}/api/v1/settings/proxy", base_url);
    if let Ok(resp) = client
        .get(&proxy_url)
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
    {
        if resp.status().is_success() {
            if let Ok(body) = resp.json::<serde_json::Value>().await {
                state.tunnel_connected = body
                    .get("connected")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                state.tunnel_has_token = body
                    .get("has_token")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                state.tunnel_url = body
                    .get("public_url")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string());
            }
        }
    }

    // Check endpoints count
    let endpoints_url = format!("{}/api/v1/endpoints/", base_url);
    if let Ok(resp) = client
        .get(&endpoints_url)
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
    {
        if resp.status().is_success() {
            if let Ok(body) = resp.json::<serde_json::Value>().await {
                if let Some(arr) = body.as_array() {
                    state.endpoint_count = arr
                        .iter()
                        .filter(|e| {
                            e.get("published")
                                .and_then(|v| v.as_bool())
                                .unwrap_or(false)
                        })
                        .count();
                }
            }
        }
    }

    state
}

/// Check if autostart is currently enabled.
fn is_autostart_enabled(app: &AppHandle) -> bool {
    use tauri_plugin_autostart::ManagerExt;
    app.autolaunch().is_enabled().unwrap_or(false)
}

/// Toggle autostart on/off.
fn toggle_autostart(app: &AppHandle) {
    use tauri_plugin_autostart::ManagerExt;
    let autolaunch = app.autolaunch();
    let currently_enabled = autolaunch.is_enabled().unwrap_or(false);

    let result = if currently_enabled {
        autolaunch.disable()
    } else {
        autolaunch.enable()
    };

    match result {
        Ok(()) => {
            log::info!(
                "Autostart toggled: {} -> {}",
                currently_enabled,
                !currently_enabled
            );
        }
        Err(e) => {
            log::error!("Failed to toggle autostart: {}", e);
        }
    }
}
