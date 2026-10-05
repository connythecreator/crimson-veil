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
```

Start the backend first: `python -m service.server`.

## Layout

```
src/main.rs       entry point (fullscreen 800x480)
src/protocol.rs   serde mirror of service/protocol.py  (unit-tested)
src/net.rs        ewebsock client, reconnect/backoff, header+binary correlation
src/hud.rs        full vector HUD via egui Painter
src/app.rs        state machine, networking glue, 15 fps frame pacing
```

## Behaviour

- Connects, retries with capped backoff until the service is up.
- On `ready` it auto-starts **continuous** scans with a debounce: frequent
  while the user interacts (`activity`), backing off when idle. Intervals are
  `CV_ACTIVE_INTERVAL_S` / `CV_IDLE_INTERVAL_S` (default 60 s / 120 s).
- **Scan effects** (`src/fx.rs`, `src/hud.rs`): while a scan runs, a fixed
  lattice of points pulses in place (they do not move — only their brightness
  shimmers); when the reconstructed PNG arrives (baked to a circular disc), a
  random cell dissolve reveals it. The field is held for a minimum time so the
  animation is watchable even on fast sim hardware.
- **Phone-style UI**: a rounded app surface with a status bar (clock +
  temperature + signal + battery, fed by the `metrics` message), an app bar
  with the title, a left navigation rail (Scan / Settings / Calibration), a
  scan disc, a bottom parameters card (intervals, electrodes, frequency,
  scan count), and a home-indicator pill.
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
