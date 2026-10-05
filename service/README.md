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
| kiosk → service | `continuous` | `on`, `active_interval_s`, `idle_interval_s` |
| kiosk → service | `activity` | — (user interaction; keeps the active interval) |
| kiosk → service | `stop` | — |
| kiosk → service | `set_freqs` | `frequencies_hz` |
| kiosk → service | `ping` | — |
| service → kiosk | `ready` | `backend`, `solver`, `n_electrodes`, `frequencies_hz` |
| service → kiosk | `boot_error` | `message` |
| service → kiosk | `progress` | `id`, `message` |
| service → kiosk | `scan_result` | `id`, `width`, `height`, `bytes` (+ binary PNG) |
| service → kiosk | `scan_error` | `id`, `message` |
| service → kiosk | `state` | `continuous`, `scanning`, `interval_s` |
| service → kiosk | `metrics` | `battery_pct`, `battery_charging`, `temp_c` (every 5 s) |
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
- A background task broadcasts `metrics` (battery + SoC temperature) every 5 s
  from `metrics.py`, which reads standard sysfs nodes (best-effort; `null` when
  absent).

## Test

```bash
.venv/bin/python -m pytest tests/test_server.py
```
