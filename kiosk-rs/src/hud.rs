//! Mobile-style HUD, drawn with egui's `Painter` in screen coordinates.
//!
//! Tuned for the 3.5" 480x320 SPI panel (CE04868): a rounded app surface with
//! a status bar (clock + battery/temp), an app bar with the title, a left
//! navigation rail (scan / settings / calibration), a content area with the
//! scan disc, a parameters card, and a home-indicator pill.
//!
//! Interactive controls use egui `Area`s; everything visual is painted for
//! pixel control.

use egui::{Align2, Color32, FontId, Pos2, Rect, Sense, Stroke, Vec2};

use crate::app::{AppState, Page};
use crate::fx::{ScanFx, GRID};

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
const APPBAR_H: f32 = 46.0;
const RAIL_W: f32 = 66.0;
const HOME_H: f32 = 12.0;

pub fn draw(
    ctx: &egui::Context,
    screen: Rect,
    state: &mut AppState,
    fx: &ScanFx,
    time_s: f32,
    image: Option<&egui::TextureHandle>,
) {
    let p = ctx.layer_painter(egui::LayerId::background());
    p.rect_filled(screen, egui::CornerRadius::ZERO, BEZEL);

    // The phone screen itself: a rounded app surface.
    let app = Rect::from_min_max(
        screen.min + Vec2::splat(SCREEN_M),
        screen.max - Vec2::splat(SCREEN_M),
    );
    p.rect_filled(app, egui::CornerRadius::same(SCREEN_R), SURFACE);

    let status = Rect::from_min_max(app.min, Pos2::new(app.right(), app.top() + STATUS_H));
    let appbar = Rect::from_min_max(
        Pos2::new(app.left(), status.bottom()),
        Pos2::new(app.right(), status.bottom() + APPBAR_H),
    );
    let rail = Rect::from_min_max(
        Pos2::new(app.left(), appbar.bottom()),
        Pos2::new(app.left() + RAIL_W, app.bottom() - HOME_H),
    );
    let content = Rect::from_min_max(
        Pos2::new(rail.right(), appbar.bottom()),
        Pos2::new(app.right(), app.bottom() - HOME_H),
    );

    status_bar(&p, status, state);
    app_bar(&p, appbar, state);
    let body = content.shrink(4.0);
    match state.page {
        Page::Scan => scan_page(&p, body, state, fx, time_s, image),
        Page::Settings => placeholder(&p, body, "Settings", "scan cadence and hardware options"),
        Page::Calibration => {
            placeholder(&p, body, "Calibration", "gain / phase calibration (deferred)")
        }
    }
    rail_nav(ctx, rail, state);
    home_indicator(&p, app);
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

    // Right cluster: temperature, wifi-ish signal, battery.
    let mut x = rect.right() - 16.0;
    battery(painter, Pos2::new(x - 20.0, cy), state);
    x -= 52.0;
    signal(painter, Pos2::new(x - 6.0, cy));
    x -= 26.0;
    if let Some(t) = state.temp_c {
        painter.text(
            Pos2::new(x, cy),
            Align2::RIGHT_CENTER,
            format!("{t:.0}\u{00b0}C"),
            FontId::monospace(11.0),
            STEEL,
        );
    }
}

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
    match state.battery_pct {
        Some(pct) => {
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
            if state.battery_charging {
                let b = body.center();
                painter.line_segment([b + Vec2::new(-2.5, -4.0), b + Vec2::new(0.5, 0.0)], Stroke::new(1.6_f32, TEXT));
                painter.line_segment([b + Vec2::new(0.5, 0.0), b + Vec2::new(-0.5, 0.0)], Stroke::new(1.6_f32, TEXT));
                painter.line_segment([b + Vec2::new(-0.5, 0.0), b + Vec2::new(2.5, 4.0)], Stroke::new(1.6_f32, TEXT));
            }
            painter.text(
                Pos2::new(body.left() - 4.0, at.y),
                Align2::RIGHT_CENTER,
                format!("{pct:.0}%"),
                FontId::monospace(9.0),
                STEEL,
            );
        }
        None => {
            painter.text(body.center(), Align2::CENTER_CENTER, "\u{2013}", FontId::monospace(9.0), STEEL);
        }
    }
}

// --- app bar ---------------------------------------------------------------

fn app_bar(painter: &egui::Painter, rect: Rect, state: &AppState) {
    // Crimson brand mark only - no wordmark (the nav rail shows where you are).
    let cx = rect.left() + 26.0;
    painter.circle_stroke(Pos2::new(cx, rect.center().y), 12.0, Stroke::new(2.4_f32, CRIM));
    painter.circle_filled(Pos2::new(cx, rect.center().y), 4.2, CRIM);
    // Current section, large.
    painter.text(
        Pos2::new(rect.left() + 50.0, rect.center().y),
        Align2::LEFT_CENTER,
        page_title(state.page),
        FontId::proportional(22.0),
        TEXT,
    );
    // A crimson accent down the left edge of the header.
    painter.rect_filled(
        Rect::from_min_max(
            Pos2::new(rect.left(), rect.top() + 6.0),
            Pos2::new(rect.left() + 2.0, rect.bottom() - 6.0),
        ),
        egui::CornerRadius::same(1),
        CRIMD,
    );
    painter.line_segment(
        [Pos2::new(rect.left(), rect.bottom()), Pos2::new(rect.right(), rect.bottom())],
        Stroke::new(1.0_f32, STEELD),
    );
}

fn page_title(page: Page) -> &'static str {
    match page {
        Page::Scan => "Scan",
        Page::Settings => "Settings",
        Page::Calibration => "Calibration",
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
    painter: &egui::Painter,
    body: Rect,
    state: &AppState,
    fx: &ScanFx,
    time_s: f32,
    image: Option<&egui::TextureHandle>,
) {
    // Parameters card along the bottom; scan disc fills the space above it.
    let chip_h = 38.0;
    let disc_area = Rect::from_min_max(body.min, Pos2::new(body.right(), body.bottom() - chip_h - 6.0));

    // Disc centred in the available area.
    let cx = disc_area.center().x;
    let cy = disc_area.center().y;
    let scan_r = (disc_area.height() / 2.0 - 20.0).min(62.0);
    let center = Pos2::new(cx, cy);
    let ring_r = scan_r + 15.0;
    let img_rect = Rect::from_center_size(center, Vec2::splat(scan_r * 2.0));

    painter.text(
        Pos2::new(body.left() + 6.0, body.top() + 3.0),
        Align2::LEFT_TOP,
        "Live reconstruction",
        FontId::proportional(11.0),
        STEEL,
    );
    // Status pill (READY / SCANNING / CONTINUOUS ...), top-right of the page.
    let (status, color) = state.connection_label();
    let pill = Rect::from_min_size(
        Pos2::new(body.right() - 8.0 - 84.0, body.top() + 5.0),
        Vec2::new(84.0, 16.0),
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

    // Parameters card (chips) across the bottom.
    let chips = Rect::from_min_max(
        Pos2::new(body.left() + 2.0, body.bottom() - chip_h),
        Pos2::new(body.right() - 2.0, body.bottom()),
    );
    card(painter, chips);
    let items: [(&str, String); 5] = [
        ("Active", format!("{:.0}s", state.active_interval_s)),
        ("Idle", format!("{:.0}s", state.idle_interval_s)),
        ("Electrodes", format!("{}", state.n_electrodes)),
        ("Freq", format!("{:.0} kHz", state.frequency_hz / 1000.0)),
        ("Scans", format!("{}", state.scan_count)),
    ];
    let cell_w = chips.width() / items.len() as f32;
    for (i, (k, v)) in items.iter().enumerate() {
        let ccx = chips.left() + cell_w * (i as f32 + 0.5);
        painter.text(
            Pos2::new(ccx, chips.top() + 9.0),
            Align2::CENTER_CENTER,
            *k,
            FontId::proportional(8.5),
            STEEL,
        );
        painter.text(
            Pos2::new(ccx, chips.top() + 24.0),
            Align2::CENTER_CENTER,
            v,
            FontId::proportional(12.0),
            TEXT,
        );
        if i > 0 {
            let x = chips.left() + cell_w * i as f32;
            painter.line_segment(
                [Pos2::new(x, chips.top() + 8.0), Pos2::new(x, chips.bottom() - 8.0)],
                Stroke::new(1.0_f32, STEELD),
            );
        }
    }
}

fn placeholder(painter: &egui::Painter, body: Rect, title: &str, sub: &str) {
    card(painter, body);
    painter.text(body.center() - Vec2::new(0.0, 8.0), Align2::CENTER_CENTER, title, FontId::proportional(16.0), TEXT);
    painter.text(body.center() + Vec2::new(0.0, 12.0), Align2::CENTER_CENTER, sub, FontId::monospace(10.0), STEEL);
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
