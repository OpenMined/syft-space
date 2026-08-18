//! Window creation and management functions

use crate::state::{PendingUpdate, UpdateWindowState, UpdateWindowType};
use tauri::{webview::WebviewWindowBuilder, AppHandle, Emitter, Manager, WebviewUrl};
use tauri_plugin_decorum::WebviewWindowExt;

#[cfg(target_os = "macos")]
use {
    cocoa::appkit::{NSColor, NSView, NSWindow},
    cocoa::base::{id, nil, NO, YES},
    objc::{msg_send, sel, sel_impl},
    tauri::{TitleBarStyle, WindowEvent},
};

#[cfg(target_os = "macos")]
pub const MACOS_TRAFFIC_LIGHTS_INSET_X: f32 = 16.0;

#[cfg(target_os = "macos")]
pub const MACOS_TRAFFIC_LIGHTS_INSET_Y: f32 = 26.0;

pub fn _setup_main_window(app: &AppHandle, url: WebviewUrl) {
    let win_builder = WebviewWindowBuilder::new(app, "main", url)
        .title("")
        .focused(true)
        .maximized(true)
        .resizable(true)
        .min_inner_size(800.0, 600.0)
        .inner_size(1200.0, 720.0);

    #[cfg(target_os = "macos")]
    let win_builder = win_builder
        .title_bar_style(TitleBarStyle::Overlay)
        .hidden_title(true);

    let _window = win_builder.build().unwrap();
    _window.create_overlay_titlebar().unwrap();

    #[cfg(target_os = "macos")]
    {
        let window_clone = _window.clone();
        let window_clone_2 = _window.clone();

        _window
            .set_traffic_lights_inset(MACOS_TRAFFIC_LIGHTS_INSET_X, MACOS_TRAFFIC_LIGHTS_INSET_Y)
            .unwrap();

        _window.on_window_event(move |event| match event {
            WindowEvent::Resized(_) | WindowEvent::ThemeChanged(_) | WindowEvent::Focused(_) => {
                window_clone
                    .set_traffic_lights_inset(
                        MACOS_TRAFFIC_LIGHTS_INSET_X,
                        MACOS_TRAFFIC_LIGHTS_INSET_Y,
                    )
                    .unwrap();
            }
            _ => {}
        });

        // macOS can reset the traffic light position while the window is initializing.
        tauri::async_runtime::spawn(async move {
            for _ in 0..15 {
                window_clone_2
                    .set_traffic_lights_inset(
                        MACOS_TRAFFIC_LIGHTS_INSET_X,
                        MACOS_TRAFFIC_LIGHTS_INSET_Y,
                    )
                    .unwrap();
                std::thread::sleep(std::time::Duration::from_secs(1));
            }
        });
    }
}

pub fn _show_about_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("about") {
        let _ = window.show();
        let _ = window.set_focus();
        return;
    }

    let _about_window = WebviewWindowBuilder::new(app, "about", WebviewUrl::App("#/about/".into()))
        .title("About Syft Space")
        .inner_size(360.0, 300.0)
        .resizable(false)
        .focused(true)
        .decorations(false)
        .build()
        .unwrap();

    #[cfg(target_os = "macos")]
    {
        let ns_window = _about_window.ns_window().unwrap() as id;
        unsafe {
            ns_window.setOpaque_(NO);
            ns_window.setBackgroundColor_(NSColor::clearColor(nil));
            let content_view: id = ns_window.contentView();
            content_view.setWantsLayer(YES);
            let layer: id = content_view.layer();
            let _: () = msg_send![layer, setCornerRadius: 10.0];
            let _: () = msg_send![layer, setMasksToBounds: true];
        }
    }
}

pub fn _show_update_window(
    app: &AppHandle,
    update_window_type: UpdateWindowType,
    version: String,
    current_version: String,
    release_notes: String,
    error: String,
    progress: usize,
) {
    let window_state = UpdateWindowState {
        update_window_type: update_window_type.clone(),
        version: version.clone(),
        current_version: current_version.clone(),
        release_notes: release_notes.clone(),
        error: error.clone(),
        progress,
    };

    let pending_update_state = app.state::<PendingUpdate>();
    *pending_update_state
        .pending_update_window_state
        .lock()
        .unwrap() = Some(window_state.clone());

    if let Some(_window) = app.get_webview_window("updates") {
        app.emit_to("updates", "update-window-state", window_state)
            .unwrap();
    } else {
        let _update_window =
            WebviewWindowBuilder::new(app, "updates", WebviewUrl::App("#/updates/".into()))
                .title("Updates")
                .inner_size(800.0, 600.0)
                .focused(true)
                .decorations(false)
                .build()
                .unwrap();

        #[cfg(target_os = "macos")]
        {
            let ns_window = _update_window.ns_window().unwrap() as id;
            unsafe {
                ns_window.setOpaque_(NO);
                ns_window.setBackgroundColor_(NSColor::clearColor(nil));
                let content_view: id = ns_window.contentView();
                content_view.setWantsLayer(YES);
                let layer: id = content_view.layer();
                let _: () = msg_send![layer, setCornerRadius: 10.0];
                let _: () = msg_send![layer, setMasksToBounds: true];
            }
        }
        // Emit state after creating, assuming frontend will pick it up or call get_window_state
        app.emit_to("updates", "update-window-state", window_state)
            .unwrap_or_else(|e| {
                log::warn!(
                    "Could not emit initial state to newly created update window: {}",
                    e
                )
            });
    }
}
