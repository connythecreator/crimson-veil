//! Mobile-style HUD, drawn with egui's `Painter` in screen coordinates.
//!
//! Tuned for the 3.5" 480x320 SPI panel (CE04868): a rounded app surface with
//! a status bar (clock + battery), a left navigation rail (scan / settings /
//! calibration), and a content area. The app bar was removed: the rail and
//! content now start directly below the status bar.
//!
//! Interactive controls use egui `Area`s; everything visual is painted for
//! pixel control.

use egui::{Align2, Color32, FontId, Pos2, Rect, Sense, Stroke, Vec2};

use crate::app::{AppState, Page, Phase};
use crate::fx::{ScanFx, GRID};

/// A control the user activated on the HUD (applied by `KioskApp`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    Scan,
    ToggleMonitor,
    CaptureBaseline,
}

// Phone palette: near-black bezel, dark app surface, raised cards.
const BEZEL: Color32 = Color32::from_rgb(1, 1, 2);
const SURFACE: Color32 = Color32::from_rgb(11, 12, 15);
const CARD: Color32 = Color32::from_rgb(20, 22, 27);
const RAIL: Color32 = Color32::from_rgb(15, 17, 21);
const CRIM: Color32 = Color32::from_rgb(224, 27, 36);
const CRIM2: Color32 = Color32::from_rgb(255, 59, 74);
const CRIMD: Color32 = Color32::from_rgb(108, 15, 21);
const STEEL: Color32 = Color32::from_rgb(126, 134, 146);
const STEELD: Color32 = Color32::from_rgb(44, 48, 55);
const OK: Color32 = Color32::from_rgb(34, 197, 94);
const WARN: Color32 = Color32::from_rgb(234, 179, 8);
const TEXT: Color32 = Color32::from_rgb(236, 239, 243);

// Layout for the 3.5" 480x320 panel (phone-style proportions).
const SCREEN_M: f32 = 6.0;
const SCREEN_R: u8 = 14;
const STATUS_H: f32 = 24.0;
const RAIL_W: f32 = 66.0;
const HOME_H: f32 = 12.0;

pub fn draw(
    ctx: &egui::Context,
    screen: Rect,
    state: &mut AppState,
    fx: &ScanFx,
    time_s: f32,
    image: Option<&egui::TextureHandle>,
) -> Option<Action> {
    let p = ctx.layer_painter(egui::LayerId::background());
    p.rect_filled(screen, egui::CornerRadius::ZERO, BEZEL);

    // The phone screen itself: a rounded app surface.
    let app = Rect::from_min_max(
        screen.min + Vec2::splat(SCREEN_M),
        screen.max - Vec2::splat(SCREEN_M),
    );
    p.rect_filled(app, egui::CornerRadius::same(SCREEN_R), SURFACE);

    // Pre-start: a full-screen terminal-style self-test. A tap is handled by
    // the app (it needs the input state), so no action is returned here.
    if state.phase == Phase::SelfTest {
        self_test_page(&p, app, state);
        return None;
    }

    let status = Rect::from_min_max(app.min, Pos2::new(app.right(), app.top() + STATUS_H));
    // No app bar: the rail and content start right below the status bar.
    let rail = Rect::from_min_max(
        Pos2::new(app.left(), status.bottom()),
        Pos2::new(app.left() + RAIL_W, app.bottom() - HOME_H),
    );
    let content = Rect::from_min_max(
        Pos2::new(rail.right(), status.bottom()),
        Pos2::new(app.right(), app.bottom() - HOME_H),
    );

    status_bar(&p, status, state);
    let body = content.shrink(4.0);
    let action = match state.page {
        Page::Scan => scan_page(ctx, &p, body, state, fx, time_s, image),
        Page::Settings => {
            settings_page(&p, body, state);
            None
        }
        Page::Calibration => calibration_page(ctx, &p, body, state),
    };
    rail_nav(ctx, rail, state);
    home_indicator(&p, app);
    action
}

// --- status bar ------------------------------------------------------------

fn status_bar(painter: &egui::Painter, rect: Rect, state: &AppState) {
    let cy = rect.center().y;
    let clock = chrono::Local::now().format("%H:%M").to_string();
    painter.text(
        Pos2::new(rect.left() + 16.0, cy),
        Align2::LEFT_CENTER,
        clock,
        FontId::proportional(14.0),
        TEXT,
    );

    // Right cluster: fuel-gauge glyph (with a charging bolt when charging),
    // the state-of-charge percentage immediately left of it, and the undershot
    // runtime to the left of that. Temperatures are shown only in Settings; the
    // signal bars are dropped for now (the `signal` fn is kept for later).
    let glyph_cx = rect.right() - 22.0;
    battery(painter, Pos2::new(glyph_cx, cy), state);

    let mut cursor = glyph_cx - 15.0; // right edge of the text column
    if let Some(pct) = state.battery_pct {
        let label = format!("{pct:.0}%");
        painter.text(
            Pos2::new(cursor, cy),
            Align2::RIGHT_CENTER,
            &label,
            FontId::monospace(11.0),
            if state.battery_charging { OK } else { STEEL },
        );
        cursor -= mono_width(&label) + 8.0;
    }
    if let Some(secs) = state.runtime_s {
        painter.text(
            Pos2::new(cursor, cy),
            Align2::RIGHT_CENTER,
            fmt_runtime(secs),
            FontId::monospace(11.0),
            STEEL,
        );
    }
}

/// Approximate advance width of a monospace string at the status-bar size.
fn mono_width(s: &str) -> f32 {
    s.chars().count() as f32 * 6.7
}

/// "2h10m" / "45m" / "3d2h".
fn fmt_runtime(secs: u32) -> String {
    let mins = secs / 60;
    let (h, m) = (mins / 60, mins % 60);
    if h >= 24 {
        format!("{}d{}h", h / 24, h % 24)
    } else if h > 0 {
        format!("{h}h{m}m")
    } else {
        format!("{m}m")
    }
}

#[allow(dead_code)] // temporarily removed from the status bar
fn signal(painter: &egui::Painter, at: Pos2) {
    // Four ascending bars (phone signal style).
    for (i, h) in [4.0_f32, 7.0, 10.0, 13.0].into_iter().enumerate() {
        let x = at.x + i as f32 * 4.0;
        painter.rect_filled(
            Rect::from_min_max(Pos2::new(x, at.y + 7.0 - h), Pos2::new(x + 2.5, at.y + 7.0)),
            egui::CornerRadius::same(1),
            if i < 3 { STEEL } else { STEELD },
        );
    }
}

fn battery(painter: &egui::Painter, at: Pos2, state: &AppState) {
    let w = 22.0;
    let h = 10.0;
    let body = Rect::from_center_size(at, Vec2::new(w, h));
    painter.rect_stroke(
        body,
        egui::CornerRadius::same(3),
        Stroke::new(1.4_f32, STEEL),
        egui::StrokeKind::Inside,
    );
    painter.rect_filled(
        Rect::from_min_size(Pos2::new(body.right() + 1.5, at.y - 2.5), Vec2::new(2.5, 5.0)),
        egui::CornerRadius::same(1),
        STEEL,
    );
    if let Some(pct) = state.battery_pct {
        let frac = (pct / 100.0).clamp(0.0, 1.0);
        let color = if pct <= 15.0 { CRIM2 } else if pct <= 35.0 { WARN } else { OK };
        painter.rect_filled(
            Rect::from_min_size(
                Pos2::new(body.left() + 2.0, body.top() + 2.0),
                Vec2::new((w - 4.0) * frac, h - 4.0),
            ),
            egui::CornerRadius::same(2),
            color,
        );
    }
    // Charging is a power lightning bolt on top of the gauge.
    if state.battery_charging {
        let b = body.center();
        painter.line_segment([b + Vec2::new(-2.0, -4.0), b + Vec2::new(0.8, 0.2)], Stroke::new(1.5_f32, TEXT));
        painter.line_segment([b + Vec2::new(0.8, 0.2), b + Vec2::new(-0.8, 0.2)], Stroke::new(1.5_f32, TEXT));
        painter.line_segment([b + Vec2::new(-0.8, 0.2), b + Vec2::new(2.0, 4.0)], Stroke::new(1.5_f32, TEXT));
    }
}

// --- left nav rail ---------------------------------------------------------

fn rail_nav(ctx: &egui::Context, rect: Rect, state: &mut AppState) {
    ctx.layer_painter(egui::LayerId::background())
        .rect_filled(rect, egui::CornerRadius::ZERO, RAIL);

    let inner = rect.shrink2(Vec2::new(5.0, 6.0));
    let items = [
        (Page::Scan, "Scan"),
        (Page::Settings, "Settings"),
        (Page::Calibration, "Calib"),
    ];
    // Spread the items evenly so they fill the whole rail height.
    let item_h = inner.height() / items.len() as f32;

    egui::Area::new(egui::Id::new("rail"))
        .fixed_pos(rect.min)
        .order(egui::Order::Middle)
        .show(ctx, |ui| {
            ui.set_min_size(rect.size());
            ui.allocate_new_ui(
                egui::UiBuilder::new().max_rect(inner),
                |ui| {
                    ui.spacing_mut().item_spacing = Vec2::ZERO;
                    ui.vertical(|ui| {
                        for (page, label) in items {
                            if rail_item(ui, page, label, state.page == page, inner.width(), item_h) {
                                state.page = page;
                            }
                        }
                    });
                },
            );
        });
}

/// A Material-style nav rail item that fills its slot: a rounded highlight with
/// a large icon and a label. Returns true when tapped.
fn rail_item(
    ui: &mut egui::Ui,
    page: Page,
    label: &str,
    selected: bool,
    width: f32,
    height: f32,
) -> bool {
    let (rect, resp) = ui.allocate_exact_size(Vec2::new(width, height), Sense::click());
    let p = ui.painter();

    let icon_c = Pos2::new(rect.center().x, rect.top() + height * 0.40);
    let icon_r = (height * 0.26).min(width * 0.34).max(9.0);

    if selected {
        p.rect_filled(
            Rect::from_center_size(icon_c, Vec2::splat(icon_r * 2.7)),
            egui::CornerRadius::same((icon_r * 1.3) as u8),
            CRIMD,
        );
    } else if resp.hovered() {
        p.rect_filled(
            Rect::from_center_size(icon_c, Vec2::splat(icon_r * 2.7)),
            egui::CornerRadius::same((icon_r * 1.3) as u8),
            CARD,
        );
    }

    let fg = if selected { CRIM2 } else { STEEL };
    draw_icon(p, icon_c, page, fg, icon_r);
    p.text(
        Pos2::new(rect.center().x, rect.bottom() - height * 0.18),
        Align2::CENTER_CENTER,
        label,
        FontId::proportional((height * 0.20).clamp(10.0, 15.0)),
        fg,
    );
    resp.clicked()
}

fn draw_icon(painter: &egui::Painter, c: Pos2, page: Page, color: Color32, r: f32) {
    let s = Stroke::new((r * 0.16).max(1.6), color);
    match page {
        Page::Scan => {
            painter.circle_stroke(c, r, s);
            painter.circle_stroke(c, r * 0.52, s);
            painter.circle_filled(c, r * 0.20, color);
        }
        Page::Settings => {
            let ring = r * 0.62;
            painter.circle_stroke(c, ring, s);
            for k in 0..8 {
                let a = std::f32::consts::TAU * k as f32 / 8.0;
                let (sn, co) = a.sin_cos();
                painter.line_segment(
                    [
                        c + Vec2::new(co * ring, sn * ring),
                        c + Vec2::new(co * r, sn * r),
                    ],
                    s,
                );
            }
            painter.circle_filled(c, r * 0.18, color);
        }
        Page::Calibration => {
            for (i, frac) in [0.30_f32, 0.72, 0.48].into_iter().enumerate() {
                let y = c.y - r * 0.6 + i as f32 * (r * 0.6);
                painter.line_segment(
                    [Pos2::new(c.x - r, y), Pos2::new(c.x + r, y)],
                    s,
                );
                painter.circle_filled(Pos2::new(c.x - r + frac * 2.0 * r, y), r * 0.2, color);
            }
        }
    }
}

// --- pages -----------------------------------------------------------------

fn card(painter: &egui::Painter, rect: Rect) {
    painter.rect_filled(rect, egui::CornerRadius::same(10), CARD);
    painter.rect_stroke(
        rect,
        egui::CornerRadius::same(10),
        Stroke::new(1.0_f32, STEELD),
        egui::StrokeKind::Inside,
    );
}

fn scan_page(
    ctx: &egui::Context,
    painter: &egui::Painter,
    body: Rect,
    state: &AppState,
    fx: &ScanFx,
    time_s: f32,
    image: Option<&egui::TextureHandle>,
) -> Option<Action> {
    // Two columns: the EIT disc on the left, controls/readouts on the right.
    let split = body.left() + body.width() * 0.58;
    let stage = Rect::from_min_max(body.min, Pos2::new(split - 6.0, body.bottom()));
    let column = Rect::from_min_max(Pos2::new(split + 2.0, body.top()), body.max);

    painter.text(
        Pos2::new(stage.left() + 6.0, body.top() + 3.0),
        Align2::LEFT_TOP,
        "Live reconstruction",
        FontId::proportional(11.0),
        STEEL,
    );

    // Disc centred in the left stage (slightly below the label).
    let center = Pos2::new(stage.center().x, stage.center().y + 4.0);
    let scan_r = (stage.height() / 2.0 - 26.0)
        .min(stage.width() / 2.0 - 14.0)
        .clamp(24.0, 62.0);
    let ring_r = scan_r + 15.0;
    let img_rect = Rect::from_center_size(center, Vec2::splat(scan_r * 2.0));

    painter.circle_filled(center, scan_r, SURFACE);
    painter.circle_stroke(center, scan_r, Stroke::new(1.5_f32, CRIMD));
    if fx.is_scanning() {
        field_diagram(painter, center, scan_r, fx, time_s);
    } else if let (true, Some(tex)) = (fx.image_available(), image) {
        painter.image(tex.id(), img_rect, Rect::from_min_max(Pos2::ZERO, Pos2::new(1.0, 1.0)), Color32::WHITE);
        if fx.is_revealing() {
            dissolve_mask(painter, center, scan_r, fx);
        }
        painter.circle_stroke(center, scan_r, Stroke::new(1.5_f32, CRIMD));
    } else {
        painter.text(center, Align2::CENTER_CENTER, "AWAITING SCAN", FontId::monospace(10.0), STEEL);
    }

    electrode_ring(painter, center, ring_r, state);

    // --- right control column ---------------------------------------------
    let (status, color) = state.connection_label();
    let pill = Rect::from_min_size(
        Pos2::new(column.left(), column.top() + 2.0),
        Vec2::new(column.width(), 16.0),
    );
    painter.rect_filled(pill, egui::CornerRadius::same(8), CARD);
    painter.circle_filled(Pos2::new(pill.left() + 9.0, pill.center().y), 2.6, color);
    painter.text(
        Pos2::new(pill.left() + 16.0, pill.center().y),
        Align2::LEFT_CENTER,
        status,
        FontId::monospace(9.0),
        color,
    );

    let mut y = pill.bottom() + 8.0;
    let btn_h = 34.0;
    let gap = 7.0;

    let scan_rect = Rect::from_min_size(Pos2::new(column.left(), y), Vec2::new(column.width(), btn_h));
    let can_scan = state.can_scan();
    let scan_enabled = can_scan && !state.continuous && !state.scanning;
    let scan_clicked = painted_button(ctx, painter, scan_rect, "SINGLE SCAN", scan_enabled, false);
    y += btn_h + gap;

    let monitor_rect = Rect::from_min_size(Pos2::new(column.left(), y), Vec2::new(column.width(), btn_h));
    let monitor_clicked = painted_button(
        ctx,
        painter,
        monitor_rect,
        if state.continuous { "STOP" } else { "MONITOR" },
        can_scan,
        state.continuous,
    );
    y += btn_h + 8.0;

    if !can_scan {
        painter.text(
            Pos2::new(column.left(), y),
            Align2::LEFT_TOP,
            "CAPTURE BASELINE IN CALIB",
            FontId::monospace(8.5),
            WARN,
        );
        y += 12.0;
    }

    // Compact readouts (moved out of the old bottom chip card).
    let rows = [
        ("Electrodes", format!("{}", state.n_electrodes)),
        ("Freq", format!("{:.0} kHz", state.frequency_hz / 1000.0)),
        ("Scans", format!("{}", state.scan_count)),
        ("Active", format!("{:.0}s", state.active_interval_s)),
        ("Idle", format!("{:.0}s", state.idle_interval_s)),
    ];
    for (key, value) in rows {
        if y + 11.0 > column.bottom() {
            break;
        }
        painter.text(
            Pos2::new(column.left(), y),
            Align2::LEFT_TOP,
            key,
            FontId::proportional(9.5),
            STEEL,
        );
        painter.text(
            Pos2::new(column.right(), y),
            Align2::RIGHT_TOP,
            value,
            FontId::monospace(9.5),
            TEXT,
        );
        y += 13.0;
    }

    if scan_clicked {
        Some(Action::Scan)
    } else if monitor_clicked {
        Some(Action::ToggleMonitor)
    } else {
        None
    }
}

/// A painted push-button with an `Area` for hit-testing (mirrors `rail_item`).
fn painted_button(
    ctx: &egui::Context,
    painter: &egui::Painter,
    rect: Rect,
    label: &str,
    enabled: bool,
    active: bool,
) -> bool {
    let id = egui::Id::new(("hud-button", label));
    let resp = egui::Area::new(id)
        .fixed_pos(rect.min)
        .order(egui::Order::Middle)
        .show(ctx, |ui| {
            let sense = if enabled { Sense::click() } else { Sense::hover() };
            ui.allocate_exact_size(rect.size(), sense).1
        })
        .inner;

    let (fill, stroke, fg) = if !enabled {
        (SURFACE, STEELD, STEELD)
    } else if active {
        (CRIMD, CRIM2, TEXT)
    } else if resp.hovered() {
        (STEELD, STEEL, TEXT)
    } else {
        (CARD, STEELD, TEXT)
    };
    painter.rect_filled(rect, egui::CornerRadius::same(8), fill);
    painter.rect_stroke(
        rect,
        egui::CornerRadius::same(8),
        Stroke::new(1.0_f32, stroke),
        egui::StrokeKind::Inside,
    );
    painter.text(
        rect.center(),
        Align2::CENTER_CENTER,
        label,
        FontId::monospace(10.5),
        fg,
    );

    enabled && resp.clicked()
}

/// Full-screen terminal-style hardware self-test (shown before the HUD).
fn self_test_page(painter: &egui::Painter, app: Rect, state: &AppState) {
    let left = app.left() + 14.0;
    let right = app.right() - 14.0;
    let mut y = app.top() + 12.0;

    painter.text(
        Pos2::new(left, y),
        Align2::LEFT_TOP,
        "CRIMSON VEIL // HARDWARE SELF-TEST",
        FontId::monospace(11.0),
        CRIM2,
    );
    y += 17.0;
    painter.line_segment(
        [Pos2::new(left, y), Pos2::new(right, y)],
        Stroke::new(1.0_f32, STEELD),
    );
    y += 9.0;

    if state.checks.is_empty() {
        let msg = if state.self_test_running {
            "RUNNING CHECKS..."
        } else {
            "WAITING FOR CONTROL SERVICE..."
        };
        painter.text(
            Pos2::new(left, y),
            Align2::LEFT_TOP,
            msg,
            FontId::monospace(10.0),
            WARN,
        );
    } else {
        for check in &state.checks {
            let (status_color, status_text) = match check.status.as_str() {
                "pass" => (OK, "PASS"),
                "fail" => (CRIM2, "FAIL"),
                "warn" => (WARN, "WARN"),
                "skip" => (STEEL, "SKIP"),
                _ => (STEEL, "----"),
            };

            painter.text(
                Pos2::new(left, y),
                Align2::LEFT_TOP,
                &check.name,
                FontId::monospace(10.5),
                TEXT,
            );
            // Dotted leader between the name and the verdict.
            let mut x = left + mono_width(&check.name) + 6.0;
            let dots_end = right - 42.0;
            while x < dots_end {
                painter.circle_filled(Pos2::new(x, y + 6.0), 0.9, STEELD);
                x += 5.0;
            }
            painter.text(
                Pos2::new(right, y),
                Align2::RIGHT_TOP,
                status_text,
                FontId::monospace(10.5),
                status_color,
            );
            y += 15.0;

            if !check.detail.is_empty() && check.status != "pass" {
                painter.text(
                    Pos2::new(left + 8.0, y),
                    Align2::LEFT_TOP,
                    &check.detail,
                    FontId::monospace(8.5),
                    STEEL,
                );
                y += 12.0;
            }
        }
    }

    let (footer, footer_color) = if state.self_test_done {
        ("TAP TO CONTINUE", OK)
    } else {
        ("TAP TO RETRY IF THE SERVICE IS OFFLINE", STEEL)
    };
    painter.text(
        Pos2::new(app.center().x, app.bottom() - 16.0),
        Align2::CENTER_CENTER,
        footer,
        FontId::monospace(10.0),
        footer_color,
    );
}

/// Calibration page: capture the measured reference pyEIT differences against.
fn calibration_page(
    ctx: &egui::Context,
    painter: &egui::Painter,
    body: Rect,
    state: &AppState,
) -> Option<Action> {
    card(painter, body);
    let left = body.left() + 10.0;
    let right = body.right() - 10.0;
    let mut y = body.top() + 8.0;

    section(painter, left, &mut y, "Reconstruction reference");
    row(painter, left, right, y, "Solver", &state.solver);
    y += 15.0;

    let status = if state.capturing_baseline {
        "capturing..."
    } else if state.baseline_ready {
        "ready"
    } else if state.solver == "pyeit" {
        "not captured"
    } else {
        "not required"
    };
    row(painter, left, right, y, "Baseline", status);
    y += 15.0;
    row(
        painter,
        left,
        right,
        y,
        "Frequency",
        &format!("{:.0} kHz", state.frequency_hz / 1000.0),
    );
    y += 18.0;

    painter.text(
        Pos2::new(left, y),
        Align2::LEFT_TOP,
        "Capture with the phantom unchanged;\nscans then show changes from it.",
        FontId::monospace(8.5),
        STEEL,
    );
    y += 26.0;

    let enabled = state.solver == "pyeit"
        && !state.capturing_baseline
        && !state.scanning
        && !state.continuous;
    let rect = Rect::from_min_size(Pos2::new(left, y), Vec2::new(right - left, 32.0));
    let label = if state.baseline_ready {
        "RECAPTURE BASELINE"
    } else {
        "CAPTURE BASELINE"
    };
    if painted_button(ctx, painter, rect, label, enabled, state.capturing_baseline) {
        Some(Action::CaptureBaseline)
    } else {
        None
    }
}

#[allow(dead_code)] // kept for any future placeholder pages
fn placeholder(painter: &egui::Painter, body: Rect, title: &str, sub: &str) {
    card(painter, body);
    painter.text(body.center() - Vec2::new(0.0, 8.0), Align2::CENTER_CENTER, title, FontId::proportional(16.0), TEXT);
    painter.text(body.center() + Vec2::new(0.0, 12.0), Align2::CENTER_CENTER, sub, FontId::monospace(10.0), STEEL);
}

/// Settings page: battery detail and every temperature sensor (the status bar
/// deliberately shows none of these).
fn settings_page(painter: &egui::Painter, body: Rect, state: &AppState) {
    card(painter, body);
    let left = body.left() + 10.0;
    let right = body.right() - 10.0;
    let mut y = body.top() + 8.0;

    section(painter, left, &mut y, "Power");
    row(painter, left, right, y, "Battery", &battery_readout(state));
    y += 15.0;
    row(
        painter,
        left,
        right,
        y,
        "Source",
        if state.battery_charging {
            "external (charging)"
        } else if state.on_battery {
            "battery"
        } else {
            "--"
        },
    );
    y += 15.0;
    row(
        painter,
        left,
        right,
        y,
        "Low-voltage cutoff",
        &state.low_v.map(|v| format!("{v:.2} V")).unwrap_or_else(|| "--".into()),
    );
    y += 15.0;
    row(painter, left, right, y, "Runtime left", &fmt_runtime_opt(state.runtime_s));
    y += 20.0;

    section(painter, left, &mut y, "Temperatures");
    row(painter, left, right, y, "Witty Pi (LM75B)", &fmt_temp(state.temp_wittypi_c));
    y += 15.0;
    row(painter, left, right, y, "ESP32", &fmt_temp(state.temp_esp32_c));
    y += 15.0;
    row(painter, left, right, y, "AD5933", &fmt_temp(state.temp_ad5933_c));
    y += 15.0;
    row(painter, left, right, y, "Pi SoC", &fmt_temp(state.temp_pi_c));
}

fn section(painter: &egui::Painter, x: f32, y: &mut f32, title: &str) {
    painter.text(Pos2::new(x, *y), Align2::LEFT_TOP, title, FontId::proportional(12.0), CRIM2);
    *y += 15.0;
}

fn row(painter: &egui::Painter, left: f32, right: f32, y: f32, key: &str, value: &str) {
    painter.text(Pos2::new(left, y), Align2::LEFT_TOP, key, FontId::proportional(10.5), STEEL);
    painter.text(Pos2::new(right, y), Align2::RIGHT_TOP, value, FontId::monospace(10.5), TEXT);
}

fn battery_readout(state: &AppState) -> String {
    match state.battery_pct {
        Some(pct) => {
            let mut s = format!("{pct:.0}%");
            if let Some(v) = state.battery_v {
                s += &format!("  {v:.2} V");
            }
            if state.battery_charging {
                s += "  charging";
            }
            s
        }
        None if state.battery_charging => "charging".to_string(),
        None => "--".to_string(),
    }
}

fn fmt_runtime_opt(secs: Option<u32>) -> String {
    match secs {
        Some(s) => format!("~{}", fmt_runtime(s)),
        None => "--".to_string(),
    }
}

fn fmt_temp(t: Option<f32>) -> String {
    match t {
        Some(c) => format!("{c:.1}\u{00b0}C"),
        None => "--".to_string(),
    }
}

fn home_indicator(painter: &egui::Painter, app: Rect) {
    let w = 72.0;
    let y = app.bottom() - 6.0;
    painter.rect_filled(
        Rect::from_center_size(Pos2::new(app.center().x, y), Vec2::new(w, 3.0)),
        egui::CornerRadius::same(2),
        STEELD,
    );
}

// --- scan disc -------------------------------------------------------------

fn electrode_ring(painter: &egui::Painter, center: Pos2, r: f32, state: &AppState) {
    painter.circle_stroke(center, r, Stroke::new(1.5_f32, STEELD));
    let n = state.n_electrodes.max(4) as usize;
    let active = if state.scanning { Some((state.frames / 2) as usize % n) } else { None };
    for k in 0..n {
        let a = std::f32::consts::TAU * k as f32 / n as f32 - std::f32::consts::FRAC_PI_2;
        let (s, c) = a.sin_cos();
        let inner = center + Vec2::new(c * (r - 5.0), s * (r - 5.0));
        let outer = center + Vec2::new(c * (r + 5.0), s * (r + 5.0));
        let lit = active == Some(k);
        painter.line_segment([inner, outer], Stroke::new(2.0_f32, if lit { CRIM2 } else { CRIM }));
        painter.circle_filled(outer, 2.0, if lit { CRIM2 } else { CRIM });
    }
}

// --- effects ---------------------------------------------------------------

fn field_diagram(painter: &egui::Painter, center: Pos2, radius: f32, fx: &ScanFx, t: f32) {
    let step = (radius * 2.0) / GRID as f32;
    let dot_r = 1.4_f32.max(step * 0.12);
    let r2 = radius * radius;
    for gy in 0..GRID {
        for gx in 0..GRID {
            let idx = gy * GRID + gx;
            let pos = Pos2::new(
                center.x - radius + (gx as f32 + 0.5) * step,
                center.y - radius + (gy as f32 + 0.5) * step,
            );
            if (pos.x - center.x).powi(2) + (pos.y - center.y).powi(2) > r2 {
                continue;
            }
            let pulse = fx.pulse(idx, t);
            let alpha = (70.0 + 165.0 * pulse) as u8;
            let color = blend(CRIMD, CRIM2, pulse);
            painter.circle_filled(pos, dot_r, Color32::from_rgba_unmultiplied(color.r(), color.g(), color.b(), alpha));
        }
    }
    painter.text(
        Pos2::new(center.x, center.y + radius - 5.0),
        Align2::CENTER_BOTTOM,
        "ACQUIRING",
        FontId::monospace(10.0),
        CRIM2,
    );
}

fn dissolve_mask(painter: &egui::Painter, center: Pos2, radius: f32, fx: &ScanFx) {
    let step = (radius * 2.0) / GRID as f32;
    let r2 = radius * radius;
    for gy in 0..GRID {
        for gx in 0..GRID {
            let idx = gy * GRID + gx;
            if fx.cell_revealed(idx) {
                continue;
            }
            let cell = Rect::from_min_size(
                Pos2::new(center.x - radius + gx as f32 * step, center.y - radius + gy as f32 * step),
                Vec2::new(step + 0.5, step + 0.5),
            );
            let c = cell.center();
            if (c.x - center.x).powi(2) + (c.y - center.y).powi(2) > r2 {
                continue;
            }
            painter.rect_filled(cell, egui::CornerRadius::ZERO, SURFACE);
        }
    }
}

fn blend(a: Color32, b: Color32, t: f32) -> Color32 {
    let t = t.clamp(0.0, 1.0);
    let l = |x: u8, y: u8| (x as f32 * (1.0 - t) + y as f32 * t) as u8;
    Color32::from_rgb(l(a.r(), b.r()), l(a.g(), b.g()), l(a.b(), b.b()))
}
