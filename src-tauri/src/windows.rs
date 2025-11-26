//! Window creation and management functions

use crate::state::{PendingUpdate, UpdateWindowState, UpdateWindowType};
use tauri::{webview::WebviewWindowBuilder, AppHandle, Emitter, Manager, WebviewUrl};

#[cfg(target_os = "macos")]
use {
    cocoa::appkit::{NSColor, NSView, NSWindow},
    cocoa::base::{id, nil, NO, YES},
    objc::{msg_send, sel, sel_impl},
};

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
