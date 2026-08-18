// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs::OpenOptions;
use std::io::Write;
use std::panic;

use dirs::home_dir;

fn main() {
    panic::set_hook(Box::new(|info| {
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(
                home_dir()
                    .expect("Failed to get home directory")
                    .join(".syft-space")
                    .join("logs")
                    .join("syft-space-desktop.log"),
            )
            .unwrap();
        writeln!(file, "Panicked: {:?}", info).unwrap();
    }));

    app_lib::run();
}
