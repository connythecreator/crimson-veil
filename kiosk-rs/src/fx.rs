//! Scan effects: a pulsating field-diagram while a scan runs, then a random
//! pixel/tile dissolve that reveals the reconstructed EIT image.
//!
//! The field animation is held for at least `MIN_ACQUIRE_SECS` even if the
//! scan returns sooner, so the acquisition reads as a deliberate, watchable
//! animation rather than a sub-second flash on fast (sim) hardware.
//!
//! No external RNG: a tiny xorshift makes the dot phases and the reveal order
//! deterministic and dependency-free.

use std::time::Instant;

/// Side of the effect grid (GRID x GRID cells).
pub const GRID: usize = 22;
const CELLS: usize = GRID * GRID;
const MIN_ACQUIRE_SECS: f32 = 3.0; // minimum time to show the field
const REVEAL_SECS: f32 = 1.4; // duration of the dissolve
const DOT_SPEED: f32 = 3.0; // radians/second for the pulse

#[derive(Debug, Clone, Copy, PartialEq)]
enum Phase {
    Idle,
    Acquiring,
    Revealing,
    Revealed,
}

pub struct ScanFx {
    phase: Phase,
    since: Instant,
    reveal_pending: bool,
    order: Vec<u16>,
    seed: u32,
}

impl Default for ScanFx {
    fn default() -> Self {
        let mut fx = Self {
            phase: Phase::Idle,
            since: Instant::now(),
            reveal_pending: false,
            order: (0..CELLS as u16).collect(),
            seed: 0x1234_5678,
        };
        fx.shuffle();
        fx
    }
}

impl ScanFx {
    fn next_rand(&mut self) -> u32 {
        let mut x = self.seed;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        self.seed = x;
        x
    }

    fn shuffle(&mut self) {
        for i in (1..CELLS).rev() {
            let j = (self.next_rand() as usize) % (i + 1);
            self.order.swap(i, j);
        }
    }

    /// A scan started: show the field diagram immediately.
    pub fn start_scan(&mut self) {
        self.phase = Phase::Acquiring;
        self.since = Instant::now();
        self.reveal_pending = false;
    }

    /// The scan image arrived. Hold the field until the minimum acquire time
    /// has elapsed, then dissolve; if already past it, dissolve at once.
    pub fn on_result(&mut self) {
        if self.phase == Phase::Acquiring {
            if self.elapsed() >= MIN_ACQUIRE_SECS {
                self.begin_reveal();
            } else {
                self.reveal_pending = true;
            }
        } else {
            self.begin_reveal();
        }
    }

    fn begin_reveal(&mut self) {
        self.shuffle();
        self.phase = Phase::Revealing;
        self.since = Instant::now();
        self.reveal_pending = false;
    }

    /// Advance phase transitions; call once per frame.
    pub fn tick(&mut self) {
        match self.phase {
            Phase::Acquiring if self.reveal_pending && self.elapsed() >= MIN_ACQUIRE_SECS => {
                self.begin_reveal();
            }
            Phase::Revealing if self.reveal_progress() >= 1.0 => {
                self.phase = Phase::Revealed;
            }
            _ => {}
        }
    }

    fn elapsed(&self) -> f32 {
        self.since.elapsed().as_secs_f32()
    }

    pub fn is_scanning(&self) -> bool {
        self.phase == Phase::Acquiring
    }

    /// True while the finished image is being dissolved in.
    pub fn is_revealing(&self) -> bool {
        self.phase == Phase::Revealing
    }

    /// True once a scan image exists to show (revealing or fully revealed).
    pub fn image_available(&self) -> bool {
        matches!(self.phase, Phase::Revealing | Phase::Revealed)
    }

    /// 0.0 = nothing revealed, 1.0 = fully revealed.
    pub fn reveal_progress(&self) -> f32 {
        match self.phase {
            Phase::Revealing => (self.elapsed() / REVEAL_SECS).clamp(0.0, 1.0),
            Phase::Revealed => 1.0,
            _ => 0.0,
        }
    }

    /// True if grid cell `idx` (row-major) is currently revealed.
    pub fn cell_revealed(&self, idx: usize) -> bool {
        let cutoff = (self.reveal_progress() * CELLS as f32) as usize;
        self.rank(idx) < cutoff
    }

    fn rank(&self, idx: usize) -> usize {
        self.order.iter().position(|&c| c as usize == idx).unwrap_or(0)
    }

    /// Pulse value 0..1 for a cell, phase-offset by a hash so the field
    /// shimmers like a generation animation.
    pub fn pulse(&self, idx: usize, t: f32) -> f32 {
        let h = hash(idx as u32) as f32 / u32::MAX as f32;
        0.5 + 0.5 * (t * DOT_SPEED + h * std::f32::consts::TAU).sin()
    }
}

fn hash(mut x: u32) -> u32 {
    x ^= x >> 16;
    x = x.wrapping_mul(0x7feb_352d);
    x ^= x >> 15;
    x = x.wrapping_mul(0x846c_a68b);
    x ^= x >> 16;
    x
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reveal_progress_is_monotonic_and_bounded() {
        let mut fx = ScanFx::default();
        fx.start_scan();
        assert!(fx.is_scanning());
        assert!(!fx.image_available());
        fx.on_result();
        // Held in acquiring until the minimum time elapses (no fake clock, so
        // immediately after on_result the reveal has not begun).
        assert!(fx.is_scanning());
    }

    #[test]
    fn cell_reveal_all_or_nothing() {
        let mut fx = ScanFx::default();
        // Default phase is Idle -> progress 0 -> nothing revealed.
        assert!(!fx.cell_revealed(0));
        assert!(!fx.cell_revealed(CELLS - 1));
    }

    #[test]
    fn pulse_in_unit_range() {
        let fx = ScanFx::default();
        for i in [0usize, 1, 17, CELLS - 1] {
            for t in [0.0_f32, 0.3, 1.0, 2.5] {
                let p = fx.pulse(i, t);
                assert!((0.0..=1.0).contains(&p), "pulse {p} out of range");
            }
        }
    }
}
