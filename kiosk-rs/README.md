# kiosk-rs — Crimson Veil native kiosk

A fullscreen [eframe/egui](https://github.com/emilk/egui) front end for the EIT
device. It talks to the Python control service (`service/`) over a localhost
WebSocket and draws the HUD as live vector graphics — the frame, electrode
ring, readouts and status are all painted with egui's `Painter`, over the
reconstructed scan.

Rust exists here because pyegui (the old Python binding) could only stack
widgets: no overlay, no colours, no frame pacing. egui proper has all three.

## Run

```bash
CV_WS_URL=ws://127.0.0.1:8765 cargo run --release
# UI work without hardware (mock visuals):
python -m service.server --dev &
cargo run --release -- --dev
```

Start the backend first: `python -m service.server`. `--dev` also accepts
`CV_DEV=1`; it skips the pre-start self-test. Pair it with `service.server
--dev` (sim hardware + stub solver) to drive the HUD with mock data.

## Layout

```
src/main.rs       entry point (fullscreen 480x320, 3.5" SPI panel)
src/protocol.rs   serde mirror of service/protocol.py  (unit-tested)
src/net.rs        ewebsock client, reconnect/backoff, header+binary correlation
src/hud.rs        full vector HUD via egui Painter
src/app.rs        state machine, networking glue, 15 fps frame pacing
```

## Behaviour

- Connects, retries with capped backoff until the service is up.
- **Pre-start self-test**: on first connect it asks the service for a hardware
  self-test and shows a terminal-style screen (`Battery`, `Belt Controller
  (ESP)`, `Impedance Subsystem`, `PyEIT`, `Control Service`) with PASS/FAIL
  verdicts. It always waits for a tap to continue; a tap after ~12 s retries
  when the service is offline. `--dev` skips this screen.
- **Controls**: `SINGLE SCAN` runs one scan; `MONITOR` toggles continuous mode
  (debounced: frequent while the user interacts via `activity`, backing off
  when idle). Intervals are `CV_ACTIVE_INTERVAL_S` / `CV_IDLE_INTERVAL_S`
  (default 60 s / 120 s). There is no auto-start.
- **Scan effects** (`src/fx.rs`, `src/hud.rs`): while a scan runs, a fixed
  lattice of points pulses in place (they do not move — only their brightness
  shimmers); when the reconstructed PNG arrives (baked to a circular disc), a
  random cell dissolve reveals it. The field is held for a minimum time so the
  animation is watchable even on fast sim hardware.
- **Phone-style UI** (no app bar/title): a rounded app surface with a status
  bar (clock + battery from `metrics`), a left navigation rail (Scan /
  Settings / Calibration), and a two-column scan page — the EIT disc on the
  left, the status pill + `SINGLE SCAN`/`MONITOR` buttons and compact readouts
  on the right — plus a home-indicator pill.
- Decodes scan PNGs straight from the binary frame into a texture (no temp
  files).
- Redraws at **15 fps** when idle, ~30 fps while an effect animates, via
  `request_repaint_after` — no busy-spin.

## Build for the Pi (aarch64)

Cross-compiled with [`cross`](https://github.com/cross-rs/cross) (Docker):

```bash
cargo install cross --locked
cross build --release --target aarch64-unknown-linux-gnu
```

The `aarch64-unknown-linux-gnu` linker is provided by the cross image, so no
toolchain is needed on the host.
