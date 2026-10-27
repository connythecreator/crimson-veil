# crimson-veil

Software/firmware suite for **Project Crimson** (ENG40011) — a prehospital
internal-bleeding detection device using EIT / bioimpedance.

The repository is the whole device, not a library: the analog front end and the
enclosure round it, the ESP32 firmware, the Python suite that drives it, and the
kiosk the operator uses. The suite is started by a single entrypoint.

## The device

A Raspberry Pi 3 runs the kiosk and the control service. An ESP32 hangs off it
over USB serial and owns the analog front end: an AD5933 impedance engine behind
a Howland current source and an instrumentation amp, switched across the
electrode ring by four CD74HC4067 muxes. The ring is built with 8 electrodes,
tetrapolar (4 mm ECG snap buttons); the firmware and its mock tables also cover
4 and 16.

A Witty Pi 4 L3V7 supplies the Pi from the battery and reports power telemetry.
The panel is a 3.5" 480x320 SPI LCD with resistive touch, rendered by the vc4
GPU and mirrored onto the SPI panel by a small fb-copy daemon.

Each `scan` returns one frame of complex impedance points from the ESP32. The
host reconstructs it with pyEIT against a measured baseline and paints the
result; continuous monitoring is the host's job, not the firmware's.

## Layout

```
main.py                 device entrypoint (starts the control service)
dev.py                  bring-up tooling (doctor, scan-once, calibrate, upload)
software/               Python suite
  interfaces/           HardwareBackend + SolverBackend contracts
  core/                 shared types + config
  reconstruction/       pyEIT solver, grid -> PNG encoding
  sim/                  simulated backend (laptop/CI) + stub solver
  pipeline.py           run_scan(): scan -> reconstruct
service/                WebSocket control surface over software.pipeline
  server.py             asyncio ws server (owns the backends)
  session.py            boot + single-flight scan session
  metrics.py            battery (Witty Pi BMS) + temps (ESP32/Pi sysfs)
  selftest.py           boot self-test, shown as the kiosk's startup screen
  protocol.py           wire protocol (mirrored by kiosk-rs/src/protocol.rs)
kiosk-rs/               native Rust/eframe kiosk UI (full vector HUD)
hardware/               ESP32 hardware backend (USB serial) + firmware upload
firmware/
  mp-firm/              production MicroPython firmware, and its mock tables
    hwtest/             standalone AD5933 bench-test firmware
  cpp-firm/             Arduino-framework sketch for capacitor bench tests
tools/                  host-side bench tools (hwtest, mock firmware over a pty)
scripts/                Pi provisioning: kiosk installer, fb-copy daemon, BMS unit
tests/                  pytest suite (runs on the sim backend)
docs/                   local-only design research and breadboard write-up (not published)
bleed/                  KiCad board (schematic + PCB) and its LTspice bench
3Dmodels/               the printed enclosures, their CAD sources and drawings
architecture-repo-wide.svg  repo-wide architecture and scan lifecycle
```

Two front ends over one core: the Rust kiosk (`kiosk-rs`) and the Python control
service (`service/`) share `software.pipeline`. The rendered diagram is
[`architecture-repo-wide.svg`](architecture-repo-wide.svg) (PNG beside it).

## Hardware

### Acquisition front end

The ESP32 is the primary interface between the hardware and the Python suite. It
owns the **hardware configuration** — AD5933 I²C, CD74HC4067 mux pin map, ring
size — and reports it on boot, so the host never hardcodes an electrode count.
It also owns the **scan process** and the gain/phase calibration: the host sends
`{"type":"scan"}` and gets one frame back in the front end's standard adjacent
order, ready for the solver.

It reports its own die temperature and the AD5933's. Battery state is not its
business — that belongs to the Witty Pi BMS on the host.

### Host, battery and panel

The Witty Pi 4 L3V7 sits between the battery and the Pi. `scripts/wittypi/` runs
as its own systemd unit (`veil-bms.service`), samples the Witty Pi over I²C with
UUGear's utilities and writes `/run/veil-bms/telemetry.json` — power mode, Vin,
5 V rail, current, LM75B temperature and the charge/standby flags. The host's
`service/metrics.py` reads that snapshot and does the battery estimate.

The 3.5" SPI panel (CE04868 / ILI9486 class) is driven by `veil-fbcp`, a
self-contained fb-copy daemon in `scripts/` that mirrors `/dev/fb0` (vc4) to
`/dev/fb1` (fbtft SPI); the XPT2046 touchscreen is bound for input. See
[`scripts/`](scripts/) and *Kiosk* below.

## Firmware

| tree | what it is |
|---|---|
| `firmware/mp-firm/` | the production MicroPython firmware — config, scan, mux, calibration, JSON protocol. Uploaded with `dev.py upload-firmware` or `mpremote`; `base_fm/` holds the stock ESP32 image |
| `firmware/mp-firm/hwtest/` | a separate, self-contained bench firmware: AD5933 I²C and a known-capacitor fixture, no mux, no pyEIT, no Pi. Produces/merges `cal.json` |
| `firmware/cpp-firm/` | an Arduino-framework sketch used to characterise the AD5933 on the bench |

The wire protocol is line-delimited JSON, documented in
[`hardware/README.md`](hardware/README.md) and implemented on both sides by
`hardware/esp32.py` and `firmware/mp-firm/src/protocol.py`. The ESP32 speaks
`hello`, `frame`, `telemetry`, `selftest_result` and `error`; the host sends
`identify`, `scan`, `stop`, `selftest`.

`tools/hwtest.py` is the host side of the bench firmware — it uploads the
`hwtest` tree if asked and talks to the ESP32 directly, with no control service,
kiosk or pyEIT in the loop. `tools/run_mock_firmware.py` runs the production
firmware's mock mode over a pty, which exercises the real `Esp32Hardware` /
`SerialTransport` path without an ESP32, AD5933 or mux bank.

## Mechanical

`3Dmodels/` holds both enclosures as parametric OpenSCAD, with the exported
STLs, renders and dimensioned drawings beside them:

| | |
|---|---|
| `case/pi-stack-v0.7.scad` | the main case: Raspberry Pi 3 + Witty Pi + 3.5" LCD, in four printed parts — base, mid, bezel and a strap plate on the underside, with the ports and the LED/switch rows cut through the front panel. `pi-stack.scad` is the v0.6 three-part predecessor |
| `case/ce07929-case.scad` | the protoboard case: two CE07929 boards side by side on their long edges, held on eight printed pinch clips that pass up through the mounting holes, with the −X end open above a 10 mm sill for the ESP32 and the rest of the end-of-board IO, and a hexagonal vent field in the lid |
| `base/`, `derived/` | vendor STEP models, and the STLs the SCAD files import |

The pi-stack case carries its own checks. `case/verify.py` ray-casts the
exported meshes rather than trusting a render: every clearance, wall, clip and
opening that the design claims is probed against the solid. `case/render.sh`
regenerates `preview/v0.7-*.png`, and `case/drawings/make_drawings.py`
regenerates the A3 SVG sheets from the same SCAD constants. The CE07929 case
was checked the same way while it was built, but has no committed script yet.

## Electronics design

`bleed/` is the KiCad project for the front-end board — schematic, PCB and
project files — and `bleed/sim/` is the LTspice bench for its excitation stage,
a mirrored Howland current pump taken from the schematic itself.

`docs/eit-bioimpedance/` is the breadboard build the firmware grew on: AD5933
with our own Howland source, instrumentation amp and four-mux bank, 8
electrodes tetrapolar, plus its BOM, netlist, pinouts and sensor placement.
`docs/InternalBleeding-Work/` holds the literature and project-brief research
behind the design. The `docs/` tree is kept locally and is not part of this
repository's published history.

The system view that ties the three together — constraints, safety argument,
measurement chain and the decisions taken — is `Subsystem Breakdown & Decisions
made.txt` at the repo root.

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

For pyEIT reconstruction, also install the optional solver (pyeit/numpy/scipy):

```bash
uv pip install --python .venv -r requirements-pyeit.txt
```

Capture a baseline in the kiosk's **CALIB** page before scanning; pyEIT
differences each frame against that measured reference. The solver contract is
in [`software/reconstruction/PYEIT_SOLVER.md`](software/reconstruction/PYEIT_SOLVER.md)
and the synthetic validation record in
[`software/reconstruction/PYEIT_VALIDATION.md`](software/reconstruction/PYEIT_VALIDATION.md).

## Run

Start the control service, then the kiosk (two terminals):

```bash
.venv/bin/python main.py                       # ws://127.0.0.1:8765
cd kiosk-rs && CV_WS_URL=ws://127.0.0.1:8765 cargo run --release

.venv/bin/python dev.py doctor                # check backends + dependencies
.venv/bin/python dev.py scan-once             # one scan -> PNG, no GUI
```

The service opens the hardware/solver backends at boot and serves scans over a
localhost WebSocket; if hardware fails to open it still serves and reports the
boot error, but scans require a successful boot. Use `service.server --dev` for
sim/stub, and see [`kiosk-rs/README.md`](kiosk-rs/README.md) for the UI.

By default the suite uses the **sim** hardware backend and **stub** solver, so
it runs end-to-end on a laptop with no hardware. Select real backends in
`software/core/config.py` (or via `CV_BACKEND` / `CV_SOLVER`).

### Mock ESP32 / firmware upload

With an ESP32 connected (CP210x `/dev/ttyUSB0`, native USB `/dev/ttyACM0`):

```bash
python dev.py upload-firmware --mock   # copy firmware + hard reset (mock front end)
python dev.py upload-firmware --mock --electrodes 16   # 4 / 8 / 16
python dev.py upload-firmware          # upload the real front-end mode
python dev.py mock-firmware            # or run the firmware on a local pty
```

`--mock` selects the synthetic AD5933/mux tables, so the full 8-electrode
40-point scan and pyEIT reconstruction work without hardware acquisition.
The first scan is the baseline; after that the mock cycles the anomaly through
eight positions, so **MONITOR** mode shows it moving once per scan (lower
`CV_ACTIVE_INTERVAL_S` / `CV_IDLE_INTERVAL_S` for a faster demo). The kiosk's
electrode ring renders exactly the count the firmware reports (`--electrodes`,
4/8/16). Without an ESP32, `dev.py mock-firmware` exposes a pty and prints the
`CV_ESP32_PORT` to use.

### Bench bring-up

The analog front end can be checked on its own, with no Pi, service or kiosk in
the loop:

```bash
python tools/hwtest.py --upload --port /dev/ttyUSB0
python tools/hwtest.py --port /dev/ttyUSB0 --f 10000 --json
python tools/hwtest.py --port /dev/ttyUSB0 --calibrate --freqs 10000,50000
```

`--calibrate` writes the gain/phase factor for a known fixture into `cal.json`,
which the production firmware reads on boot. See
[`firmware/mp-firm/hwtest/README.md`](firmware/mp-firm/hwtest/README.md) for the
fixture wiring and I²C pins.

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
`crimson-veil-backend.service` and the BMS sampler as `veil-bms.service`. It is
idempotent and backs up every file it touches; see `--help` for flags
(`--dry-run`, `--skip-splash`, `--no-pip`, `--display`, ...).

### Display: 3.5" SPI panel (default) or 7" DSI/HDMI

`--display spi35` (default) lights the **3.5" 480x320 SPI panel (CE04868 /
ILI9486 class)**. The vc4 GPU renders the kiosk at native 480x320 with hardware
GL and `veil-fbcp` (a small, self-contained fb-copy daemon; source in
`scripts/veil-fbcp.c`) mirrors `/dev/fb0` (vc4) to `/dev/fb1` (fbtft SPI). The
resistive XPT2046 touchscreen is bound for input. This does **not** use
fbcp-ili9341, which is DispmanX/32-bit-only and dead on Trixie 64-bit.

`--display dsi7` keeps the original 7" 800x480 DSI/HDMI KMS panel (no mirror).

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

The suite runs on the sim backend. It covers the pipeline, the service
protocol and metrics, the ESP32 transport (against a mock), and the bench
tools' protocol handling, so nothing needs an ESP32 or a Pi to run. The
mechanical checks are separate and need OpenSCAD:

```bash
cd 3Dmodels/case && python3 verify.py
```

## Extending

- **Hardware**: the ESP32 backend lives in `hardware/esp32.py`; the firmware is
  `firmware/mp-firm/`. To add another transport (e.g. a network node),
  implement `HardwareBackend` from `software/interfaces/hardware.py`.
- **Reconstruction** (pyEIT/EIDORS): implement `SolverBackend` from
  `software/interfaces/solver.py`.
- **Mechanical**: the cases are parametric; the tunables sit at the top of each
  `.scad`. Copy the pi-stack's approach for a new one: probe the exported mesh
  with `case/verify.py` rather than judging the change from a render.
