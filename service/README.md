# service/ — Crimson Veil control surface

A localhost WebSocket server over [`software.pipeline`](../software/pipeline.py).
It owns the boot-opened hardware and solver backends and serves scans to the
native Rust kiosk (`kiosk-rs`) — and, later, to any companion/web front end.

This is the "one core, two front ends" surface: the native Rust kiosk and this
service share `software.pipeline`.

## Run

```bash
python -m service.server                 # ws://127.0.0.1:8765
python -m service.server --port 9000
```

On the device this runs as `crimson-veil-backend.service` (installed by
`scripts/setup-pi-kiosk.sh`). `main.py` is a thin wrapper that starts it.

## Protocol

JSON text frames for control; a scan PNG is sent as **one binary frame
immediately after** its `scan_result` header (order-preserving, no base64).
The single source of truth is [`protocol.py`](protocol.py); the Rust side
mirrors it in `kiosk-rs/src/protocol.rs`.

| direction | type | fields |
| --- | --- | --- |
| kiosk → service | `hello` | `client`, `protocol` |
| kiosk → service | `scan` | `id` |
| kiosk → service | `capture_baseline` | `id` (pyEIT reference) |
| kiosk → service | `continuous` | `on`, `active_interval_s`, `idle_interval_s` |
| kiosk → service | `activity` | — (user interaction; keeps the active interval) |
| kiosk → service | `stop` | — |
| kiosk → service | `set_frequency` | `frequency_hz` |
| kiosk → service | `self_test` | — (runs the pre-start hardware checks) |
| kiosk → service | `upload_firmware` | `mock`, `electrodes` (copy firmware to the ESP, reset, reboot) |
| kiosk → service | `ping` | — |
| service → kiosk | `ready` | `backend`, `solver`, `n_electrodes`, `frequency_hz`, `baseline_ready` |
| service → kiosk | `baseline_captured` | `id`, `frequency_hz`, `n_electrodes` |
| service → kiosk | `boot_error` | `message` |
| service → kiosk | `progress` | `id`, `message` |
| service → kiosk | `scan_result` | `id`, `width`, `height`, `bytes` (+ binary PNG) |
| service → kiosk | `scan_error` | `id`, `message` |
| service → kiosk | `state` | `continuous`, `scanning`, `interval_s` |
| service → kiosk | `metrics` | `battery_pct`, `battery_charging`, `on_battery`, `battery_v`, `runtime_s`, `low_v`, `temp_wittypi_c`, `temp_esp32_c`, `temp_ad5933_c`, `temp_pi_c` (every 5 s) |
| service → kiosk | `self_test_result` | `checks: [{name, status, detail}, …]` |
| service → kiosk | `firmware_uploaded` | `port`, `files`, `mock`, `electrodes` |
| service → kiosk | `pong` | — |

## Design

- **One `ScanSession`** (`session.py`) holds the backends and runs one scan at
  a time; a concurrent request yields `scan_error: busy`.
- Blocking pipeline work runs via `asyncio.to_thread` — never on the event loop.
- **Continuous mode is server-driven and debounced**: after `continuous{on}`,
  the server scans, then waits `active_interval_s` if the client sent
  `activity` within `ACTIVITY_TIMEOUT_S`, otherwise `idle_interval_s`
  (defaults 60 s active / 120 s idle). It repeats until `stop` or disconnect.
- If boot fails the server still serves, replying `boot_error`; scans fall back
  to the configured sim defaults so the UI degrades rather than dies.
- **Self-test** (`selftest.py`) runs on `self_test`: it retries `session.boot()`
  once (so hot-plugged hardware can come up), then reports `Battery` (Witty Pi
  BMS freshness), `Belt Controller (ESP)` (ESP `identify`/`hello`),
  `Impedance Subsystem` (firmware `selftest`: AD5933 + mux), `PyEIT`
  (installed/selected) and `Control Service`. Failures are reported, not raised.
- **Firmware upload** (`upload_firmware`): closes the session to free the serial
  port, copies the MicroPython files with `mpremote`, hard-resets the ESP, and
  re-boots the session. `mock=true` selects the synthetic AD5933/mux tables.
- `python -m service.server --dev` forces the **sim** hardware + **stub** solver
  for mock visuals (pair with `crimson-veil-kiosk --dev`).
- A background task broadcasts `metrics` every 5 s from `metrics.py`. Battery
  comes from the **Witty Pi BMS** snapshot (`/run/veil-bms/telemetry.json`),
  with state-of-charge and runtime *estimated* from voltage + draw (the L3V7 has
  no fuel gauge); 0 % is anchored at the configured low-voltage threshold.
  Temperatures come from the Witty Pi LM75B, the ESP32 and AD5933 (via ESP32
  telemetry) and the Pi SoC sysfs zone. All values are best-effort (`null` when
  absent); a sysfs battery fallback keeps a bare laptop/dev host working.
- Runtime **undershoots**: it reports the *lowest* estimate seen in the last
  `CV_RUNTIME_WINDOW_S` (default 300 s) so the indicator never overpromises. A
  boot-time voltage sag can therefore pin it low until that sample ages out.

## Test

```bash
.venv/bin/python -m pytest tests/test_server.py
```
