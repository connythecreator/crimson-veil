//! Crimson Veil native kiosk entry point.
//!
//! Fullscreen eframe/egui front end. Connects to the Python control service
//! (default `ws://127.0.0.1:8765`, override with `CV_WS_URL`) and renders the
//! EIT HUD with live readouts over the reconstructed scan.

mod app;
mod fx;
mod hud;
mod net;
mod protocol;

use app::KioskApp;

const DEFAULT_URL: &str = "ws://127.0.0.1:8765";

fn main() -> eframe::Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let url = std::env::var("CV_WS_URL").unwrap_or_else(|_| DEFAULT_URL.to_string());
    let native_options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_fullscreen(true)
            .with_resizable(false)
            .with_inner_size([800.0, 480.0])
            .with_title("Crimson Veil - EIT"),
        ..Default::default()
    };

    eframe::run_native(
        "Crimson Veil - EIT",
        native_options,
        Box::new(move |_cc| Ok(Box::new(KioskApp::new(&url)))),
    )
}
