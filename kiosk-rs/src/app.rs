//! Kiosk application: state machine, networking glue, and egui frame.

use std::time::{Duration, Instant};

use eframe::egui;
use egui::{Color32, ColorImage, TextureHandle, TextureOptions};

use crate::fx::ScanFx;
use crate::hud;
use crate::net::{Net, NetEvent};
use crate::protocol::{ClientMessage, ServerMessage};

pub const FPS: u64 = 15;
pub const FRAME: Duration = Duration::from_millis(1000 / FPS);
// Effects animate at a higher cadence for smoothness (Pi 3 can afford this
// briefly): ~30 fps while scanning/revealing.
pub const ANIM_FRAME: Duration = Duration::from_millis(33);
// Debounce intervals (seconds): scan often while the user is interacting,
// back off when idle. The server enforces these; sent on continuous start.
// Overridable via CV_ACTIVE_INTERVAL_S / CV_IDLE_INTERVAL_S for testing.
pub fn active_interval_s() -> f64 {
    env_f64("CV_ACTIVE_INTERVAL_S", 60.0)
}
pub fn idle_interval_s() -> f64 {
    env_f64("CV_IDLE_INTERVAL_S", 120.0)
}
fn env_f64(key: &str, default: f64) -> f64 {
    std::env::var(key).ok().and_then(|v| v.parse().ok()).unwrap_or(default)
}

/// Turn a scan PNG into a circular disc: find the content bounding box, crop
/// a square centred on it, and bake a hard circular alpha so the black padding
/// corners disappear. The reconstruction fills a circle, so the box is the
/// content's extent.
fn to_disc(src: &image::RgbaImage) -> ColorImage {
    let (w, h) = (src.width() as i32, src.height() as i32);
    if w == 0 || h == 0 {
        return ColorImage::default();
    }
    let lum = |p: &image::Rgba<u8>| (p[0] as u32 + p[1] as u32 + p[2] as u32) / 3;

    // Content bounds: pixels brighter than the near-black background.
    let (mut minx, mut miny, mut maxx, mut maxy) = (w, h, -1i32, -1i32);
    for y in 0..h {
        for x in 0..w {
            if lum(src.get_pixel(x as u32, y as u32)) > 18 {
                minx = minx.min(x);
                miny = miny.min(y);
                maxx = maxx.max(x);
                maxy = maxy.max(y);
            }
        }
    }
    if maxx < 0 {
        // All black: just mask the whole square to a circle.
        minx = 0;
        miny = 0;
        maxx = w - 1;
        maxy = h - 1;
    }

    let (cx, cy) = ((minx + maxx) as f32 / 2.0, (miny + maxy) as f32 / 2.0);
    // Inscribed square side = the smaller content extent (the body is round).
    let side = ((maxx - minx).min(maxy - miny)).max(2) as f32;
    let radius = side / 2.0;
    let out = side as usize;
    let mut pixels = vec![egui::Color32::TRANSPARENT; out * out];
    let r2 = radius * radius;

    for oy in 0..out {
        for ox in 0..out {
            let dx = ox as f32 + 0.5 - radius;
            let dy = oy as f32 + 0.5 - radius;
            if dx * dx + dy * dy > r2 {
                continue; // outside the disc -> transparent
            }
            let sx = (cx + dx).round().clamp(0.0, (w - 1) as f32) as u32;
            let sy = (cy + dy).round().clamp(0.0, (h - 1) as f32) as u32;
            let p = src.get_pixel(sx, sy);
            pixels[oy * out + ox] = egui::Color32::from_rgb(p[0], p[1], p[2]);
        }
    }

    ColorImage {
        size: [out, out],
        pixels,
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Connection {
    Connecting,
    Connected,
}

/// Left-hand menu destinations.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Page {
    Scan,
    Settings,
    Calibration,
}

pub struct AppState {
    pub connection: Connection,
    pub page: Page,
    pub backend: String,
    pub solver: String,
    pub n_electrodes: u32,
    pub frequencies_hz: Vec<f64>,
    pub top_freq_hz: f64,
    pub active_interval_s: f64,
    pub idle_interval_s: f64,
    pub scanning: bool,
    pub continuous: bool,
    pub scan_count: u32,
    pub last_result: Option<Instant>,
    pub boot_error: Option<String>,
    pub last_error: Option<String>,
    pub frames: u64,
    // Device metrics.
    pub battery_pct: Option<f32>,
    pub battery_charging: bool,
    pub temp_c: Option<f32>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            connection: Connection::Connecting,
            page: Page::Scan,
            backend: "connecting...".into(),
            solver: "-".into(),
            n_electrodes: 8,
            frequencies_hz: Vec::new(),
            top_freq_hz: 0.0,
            active_interval_s: active_interval_s(),
            idle_interval_s: idle_interval_s(),
            scanning: false,
            continuous: false,
            scan_count: 0,
            last_result: None,
            boot_error: None,
            last_error: None,
            frames: 0,
            battery_pct: None,
            battery_charging: false,
            temp_c: None,
        }
    }
}

impl AppState {
    pub fn connection_label(&self) -> (String, Color32) {
        if let Some(err) = &self.boot_error {
            return (format!("BOOT ERROR  ({err})"), Color32::from_rgb(255, 59, 74));
        }
        if let Some(err) = &self.last_error {
            return (format!("SCAN ERROR  ({err})"), Color32::from_rgb(255, 59, 74));
        }
        let base = match self.connection {
            Connection::Connecting => "CONNECTING".to_string(),
            Connection::Connected => {
                if self.scanning {
                    "SCANNING".to_string()
                } else if self.continuous {
                    "CONTINUOUS".to_string()
                } else {
                    "READY".to_string()
                }
            }
        };
        let color = match self.connection {
            Connection::Connecting => Color32::from_rgb(234, 179, 8),
            Connection::Connected => Color32::from_rgb(34, 197, 94),
        };
        (base, color)
    }
}

pub struct KioskApp {
    net: Net,
    state: AppState,
    texture: Option<TextureHandle>,
    pending_image: Option<ColorImage>,
    fx:ScanFx,
    auto_started: bool,
    started: Instant,
}

impl KioskApp {
    pub fn new(url: &str) -> Self {
        Self {
            net: Net::new(url),
            state: AppState::default(),
            texture: None,
            pending_image: None,
            fx: ScanFx::default(),
            auto_started: false,
            started: Instant::now(),
        }
    }

    fn handle(&mut self, event: NetEvent) {
        match event {
            NetEvent::Connected => self.state.connection = Connection::Connected,
            NetEvent::Disconnected => {
                self.state.connection = Connection::Connecting;
                self.state.boot_error = None;
            }
            NetEvent::Server(msg) => self.handle_server(msg),
            NetEvent::Image { id, width, height, png } => match image::load_from_memory(&png) {
                Ok(img) => {
                    let rgba = img.to_rgba8();
                    if width != rgba.width() || height != rgba.height() {
                        log::warn!(
                            "scan {id}: header {width}x{height} != PNG {}x{}",
                            rgba.width(),
                            rgba.height()
                        );
                    }
                    self.pending_image = Some(to_disc(&rgba));
                }
                Err(err) => log::warn!("failed to decode scan {id} PNG: {err}"),
            },
        }
    }

    fn handle_server(&mut self, msg: ServerMessage) {
        match msg.kind.as_str() {
            "ready" => {
                self.state.backend = msg.backend;
                self.state.solver = msg.solver;
                self.state.n_electrodes = msg.n_electrodes;
                self.state.frequencies_hz = msg.frequencies_hz.clone();
                self.state.top_freq_hz = msg.frequencies_hz.iter().cloned().fold(0.0_f64, f64::max);
                self.state.boot_error = None;
                if !self.auto_started {
                    self.auto_started = true;
                    self.net.send(&ClientMessage::Continuous {
                        on: true,
                        active_interval_s: self.state.active_interval_s,
                        idle_interval_s: self.state.idle_interval_s,
                    });
                }
            }
            "metrics" => {
                self.state.battery_pct = msg.battery_pct;
                self.state.battery_charging = msg.battery_charging;
                self.state.temp_c = msg.temp_c;
            }
            "boot_error" => self.state.boot_error = Some(msg.message),
            "scan_error" => {
                self.state.last_error = Some(msg.message);
                self.state.scanning = false;
            }
            "progress" => {
                self.state.scanning = true;
                self.fx.start_scan();
            }
            "state" => {
                self.state.continuous = msg.continuous;
                self.state.scanning = msg.scanning;
                if msg.scanning {
                    self.fx.start_scan();
                }
            }
            "scan_result" => {
                self.state.scanning = true; // animating until the image frame lands
                self.fx.start_scan();
            }
            _ => {}
        }
    }
}

impl eframe::App for KioskApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Any input counts as activity: ask the server to stay on the active
        // (frequent) scan interval.
        let interacting = ctx.input(|i| {
            i.pointer.any_down()
                || i.pointer.any_released()
                || i.raw_scroll_delta != egui::Vec2::ZERO
                || !i.events.is_empty()
        });
        if interacting {
            self.net.send(&ClientMessage::Activity);
        }

        for event in self.net.poll() {
            self.handle(event);
        }

        self.fx.tick();
        // Keep repainting faster than the pacing cadence while an effect runs,
        // so the field/dissolve animate smoothly.
        let animating = self.fx.is_scanning() || self.fx.is_revealing();

        if let Some(color) = self.pending_image.take() {
            let size = color.size;
            self.texture = Some(ctx.load_texture("scan", color, TextureOptions::LINEAR));
            self.state.scan_count += 1;
            self.state.last_result = Some(Instant::now());
            self.state.last_error = None;
            // Hold the field for its minimum time, then dissolve the image in.
            self.fx.on_result();
            log::info!("scan #{} received ({}x{})", self.state.scan_count, size[0], size[1]);
        }

        ctx.set_visuals(egui::Visuals::dark());
        let screen = ctx.screen_rect();
        let time_s = self.started.elapsed().as_secs_f32();
        hud::draw(ctx, screen, &mut self.state, &self.fx, time_s, self.texture.as_ref());

        self.state.frames += 1;
        // Frame pacing: repaint at FPS while idle; a smoother cadence while an
        // effect animates so the field/dissolve do not stutter.
        let cadence = if animating { ANIM_FRAME } else { FRAME };
        ctx.request_repaint_after(cadence);
    }
}
