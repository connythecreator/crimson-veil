# crimson-veil

Software/firmware suite for **Project Crimson** (ENG40011) — a prehospital
internal-bleeding detection device using EIT / bioimpedance. 

The suite is not a library: it is the full device software, started by a single
entrypoint.

## Layout

```
main.py                 device entrypoint (starts the control service)
dev.py                  bring-up tooling (doctor, scan-once, calibrate)
software/               Python suite
  interfaces/           HardwareBackend + SolverBackend contracts
  core/                 shared types + config
  acquisition/          electrode roles, sequencing, calibration
  reconstruction/       grid -> PNG encoding
  sim/                  simulated backend (laptop/CI) + stub solver
  pipeline.py           run_scan(): plan -> measure -> calibrate -> reconstruct
service/                WebSocket control surface over software.pipeline
  server.py             asyncio ws server (owns the backends)
  session.py            boot + single-flight scan session
  metrics.py            battery/temperature (ESP32 telemetry + sysfs fallback)
  protocol.py           wire protocol (mirrored by kiosk-rs/src/protocol.rs)
kiosk-rs/               native Rust/eframe kiosk UI (full vector HUD)
hardware/               ESP32 hardware backend (USB serial)
firmware/               ESP32 Arduino sketch (you manage it)
tests/                  pytest suite (runs on the sim backend)
```

Two front ends over one core: the Rust kiosk (`kiosk-rs`) and the Python
control service (`service/`) share `software.pipeline`.

The physical front end is driven by an **ESP32** over USB serial. The ESP32 owns
the hardware configuration and runs single-shot scans; the host owns the scan
plan and continuous mode. See [`hardware/README.md`](hardware/README.md).

## Setup

Requires Python 3.11+ (3.12 on dev machines, 3.13 on Raspberry Pi OS Trixie).
[`uv`](https://docs.astral.sh/uv/) is recommended.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
```

On a Raspberry Pi, add the device dependencies:

```bash
uv pip install --python .venv -r requirements.txt -r requirements-pi.txt
```

## Run

Start the control service, then the kiosk (two terminals):

```bash
.venv/bin/python main.py            # control service: ws://127.0.0.1:8765
CV_WS_URL=ws://127.0.0.1:8765 .venv/bin/python -m kiosk  # (see kiosk-rs)

.venv/bin/python dev.py doctor      # check backends + dependencies
.venv/bin/python dev.py scan-once   # one scan -> PNG, no GUI
```

The kiosk is now the native Rust UI: build/run it from `kiosk-rs/` (see
[`kiosk-rs/README.md`](kiosk-rs/README.md)). The service opens the
hardware/solver backends at boot and serves scans over a localhost WebSocket;
if hardware fails to open it still serves and scans fall back to the sim.

By default the suite uses the **sim** hardware backend and **stub** solver, so
it runs end-to-end on a laptop with no hardware. Select real backends in
`software/core/config.py` (or via `CV_BACKEND` / `CV_SOLVER`).

## Kiosk (Raspberry Pi)

`scripts/setup-pi-kiosk.sh` turns a headless Raspberry Pi OS Lite (Trixie,
64-bit) install into a single-app kiosk: a custom PNG boot splash that stays
up for the whole boot (drawing boot log lines one at a time on top of it),
then console autologin, Xorg + openbox, and the native Rust kiosk.

```bash
sudo bash scripts/setup-pi-kiosk.sh --splash logo.png --binary crimson-veil-kiosk
```

It installs the X/Plymouth/GL packages, writes a small custom Plymouth theme
that scales your PNG and appends each boot message as a line
(`veil-bootlog.service` tails the journal and pushes lines with
`plymouth display-message`), rebuilds the initrd, un-quiets the kernel, and
wires `~/.bash_profile` -> `startx` -> `~/.xinitrc` -> the kiosk binary. The
splash is retained (`plymouth quit --retain-splash`) right up to the X
handover. It also installs the Python control service as
`crimson-veil-backend.service`. It is idempotent and backs up every file it
touches; see `--help` for flags (`--dry-run`, `--skip-splash`, `--no-pip`,
...).

> Plymouth can only show one surface, so a stock theme cannot show a logo and
> scrolling console text together. The custom theme instead draws the PNG and
> appends each boot message as a line, one at a time, for the entire boot.
> The kernel is not quieted, so the real logs remain on the console as a
> fallback if the handover is ever delayed.

> The kiosk is native Rust (eframe/egui) so it can draw a live vector HUD
> (overlay + colours + proper frame pacing) and talk to the Python service over
> a WebSocket. See `kiosk-rs/README.md`.

## Test

```bash
.venv/bin/python -m pytest
```

## Extending

- **Hardware**: the ESP32 backend lives in `hardware/esp32.py`; the firmware is
  the matching Arduino sketch in `firmware/`. To add another transport (e.g. a
  network node), implement `HardwareBackend` from
  `software/interfaces/hardware.py`.
- **Reconstruction** (pyEIT/EIDORS): implement `SolverBackend` from
  `software/interfaces/solver.py`.
