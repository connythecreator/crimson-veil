# hardware/ — ESP32 hardware backend

The physical front end (AD5933 + CD74HC4067 mux bank) is driven by an **ESP32**.
It is the primary interface between the hardware and the Python suite, wired to
the host over **USB serial**.

```
ESP32  ──USB serial (115200)──  Python host (service/)
  │  AD5933 (I²C)                     hardware/esp32.py
  │  4× CD74HC4067 mux               software.pipeline
```

## As-built front end

The parts-limited build uses:

- **AD5933** at 3.3 V, **1 Vpp** excitation.
- **Mirrored Howland** (TL082, ±5 V) biased at **2.5 V**.
- **AD620** on ±5 V, REF at **1.65 V** (AD5933 VDD/2), RG trimmer ≈26 kΩ
  (G ≈ 2.9).
- **Four CD74HC4067** muxes at 3.3 V, `~E` tied low (always enabled),
  `S3` tied low, non-latching, with **independent** 3-bit address buses.

| Role | S0 | S1 | S2 |
|---|---:|---:|---:|
| Drive+ | GPIO25 | GPIO33 | GPIO32 |
| Drive− | GPIO14 | GPIO27 | GPIO26 |
| Sense+ | GPIO16 | GPIO17 | GPIO19 |
| Sense− | GPIO18 | GPIO23 | GPIO13 |

The drive/sense signal at the muxes is about 2.0–3.0 V, inside the 3.3 V mux
rails. The firmware sets each role independently; there is no enable line to
toggle. `stop` powers down the AD5933 and parks all four roles on electrode 0.
See [`docs/eit-bioimpedance/README.md`](../docs/eit-bioimpedance/README.md) for
the full as-built description.

## `esp32.py`

`Esp32Hardware` implements `software.interfaces.hardware.HardwareBackend`:

- **`open`** — opens the serial port and reads the ESP32's `hello`, learning
  `n_electrodes`, the electrode list, the firmware version and the scan
  frequency. The **ESP32 owns the hardware configuration** (pin maps, mux
  wiring, ring size); the host never hardcodes it.
- **`identify`** — `esp32:/dev/ttyACM0` (or whatever port is configured).
- **`scan`** — sends `{"type":"scan"}` and returns the frame. The **ESP32 owns
  the scan process** (the electrode pairs and their order) and **calibration**;
  the host does not send a plan and does not calibrate. Points come back in the
  front end's standard adjacent order, ready for the solver.
- **`telemetry`** — returns the most recent on-chip temperature reading the
  ESP32 has pushed (`temp_esp32_c`, `temp_ad5933_c`). **Battery** state is no
  longer reported here: it is owned by the **Witty Pi 4 L3V7 BMS** on the host
  (see below and `service/metrics.py`).

The ESP32 runs **single-shot** scans only; continuous mode is a host concern and
lives in `service/`.

## Wire protocol (USB CDC, line-delimited JSON)

One JSON object per line. See the module docstring in `esp32.py` for the
authoritative description; the firmware must match it.

| host → ESP32 | purpose |
|---|---|
| `{"type":"identify"}` | ask the ESP32 to (re-)announce itself |
| `{"type":"scan"}` | execute one single-shot scan (optional `"f": Hz` to override the frequency) |
| `{"type":"selftest"}` | verify the AD5933, mux continuity and calibration, and report `selftest_result` |
| `{"type":"mux_test"}` | select each electrode on all four roles and report the loop impedance; optional `"f"`, `"min_raw"`, `"d_neg"` |
| `{"type":"stop"}` | abort / release |

| ESP32 → host | purpose |
|---|---|
| `{"type":"hello","firmware":str,"n_electrodes":int,"electrodes":[…],"sweep_hz":float}` | sent unsolicited on boot, and in reply to `identify` |
| `{"type":"frame","points":[{"n":int,"f":Hz,"re":float,"im":float}, …]}` | one frame, the firmware's adjacent sequence, `n` = index in that sequence |
| `{"type":"telemetry","temp_esp32_c":float\|null,"temp_ad5933_c":float\|null}` | periodic on-chip temperatures |
| `{"type":"selftest_result","firmware":str,"ad5933":bool,"mux":bool,"temp_ad5933_c":float\|null,"calibration":bool\|null,"calibration_entries":int\|null,"calibration_error":str\|null,"error":str\|null}` | reply to `selftest`; `mux` is false when any electrode reads open in the all-roles continuity check; `calibration` is false when `cal.json` is missing/invalid |
| `{"type":"mux_test_result","frequency_hz":float,"min_raw":float,"d_neg":int\|null,"calibration":bool,"points":[{"e":int,"drive_neg":int,"raw_re":float,"raw_im":float,"raw_abs":float,"status":str,"z_re":float?,"z_im":float?,"z_abs":float?}, …]}` | reply to `mux_test`; `status` is `connected` when `raw_abs >= min_raw`, otherwise `open` |
| `{"type":"error","message":str}` | a fault the host should surface |

The `mux_test` command is for the bench check where only electrode 0 is wired:
it sets Drive+ / Sense+ / Sense− to each electrode and Drive− to the same
electrode (or to `d_neg` when supplied). The D− C0/C1 short has been fixed, so
the test uses the same electrode for all four roles (`d_neg` is omitted by
default in `tools/mux_test.py`). Electrode 0 should read connected and all other electrodes
open. The current `cal.json` is applied when valid but is never modified.

The production `selftest` runs the same continuity cycle across every electrode
and reports `mux: false` with the open electrodes named in `error`. A failed
self-test also flashes the status LED on GPIO2 (active-high, 5 Hz) for five
seconds. The LED is driven low at boot.

## Configuration

| env | default | meaning |
|---|---|---|
| `CV_BACKEND` | `sim` | set to `esp32` to use this backend |
| `CV_ESP32_PORT` | auto | USB serial device; auto prefers CP210x/CH340/Espressif by USB ID |
| `CV_ESP32_BAUD` | `115200` | serial baud |
| `CV_FREQUENCY_HZ` | `50000` | fallback scan frequency (the `hello` value wins) |

Install the device dependency with `requirements-pi.txt` (`pyserial`). The
service account needs access to the serial device (add it to the `dialout`
group).

## Witty Pi 4 L3V7 battery management (BMS)

Power and battery are managed by a **Witty Pi 4 L3V7** HAT (UUGear). It has no
coulomb-counter fuel gauge: it measures the battery/rail voltage and output
current, reads an LM75B temperature, and enforces a configurable low-voltage
shutdown. `scripts/setup-pi-kiosk.sh` (`install_wittypi`) installs UUGear's
software with our overlay:

- **`scripts/wittypi/`** — a patched `utilities.sh` (**only** change:
  `SYSUP_PIN` 17 → 16), the `veil-bms.sh` sampler and `veil-bms.service`.
- **UWI is suppressed.** UUGear's installer normally ends by installing UWI (a
  `websocketd` web UI on :8000); the setup script strips that step and
  defensively disables any pre-existing `uwi` unit.

### Pin map (BCM)

| signal | GPIO | notes |
|---|---|---|
| HALT | 4 | host shutdown request to the Witty Pi |
| SYS_UP | **16** | Witty Pi wake pulse — moved off 17 (see below) |
| CHRG | 5 | charging (active-low input) |
| STDBY | 6 | charge-complete (active-low input) |
| I²C (SDA/SCL) | 2 / 3 | Witty Pi answers at **0x08** |

**GPIO-17 is the 3.5" panel's XPT2046 touch PENIRQ**, so SYS_UP must move to 16
(hardware trace + `SYSUP_PIN` in `utilities.sh`). GPIO-14 (the Witty Pi's
monitor/TXD) is unused here.

### `veil-bms.service`

An **independent** systemd unit (does not depend on the kiosk or backend, so
battery management survives a UI crash). `veil-bms.sh` samples every 5 s and
writes an atomic JSON snapshot to `/run/veil-bms/telemetry.json`:

```
{ ts, power_mode, vin_v, vout_v (5 V rail), iout_a, temp_c (LM75B),
  charging, standby, low_v }
```

`power_mode` is `1` on battery, `0` on USB without a battery reading, and `2`
on USB with the battery connected/charging. `service/metrics.py` reads it, estimates **state-of-charge** and **runtime**
from voltage + draw (anchored at `low_v` = 0 %), and merges in the ESP32 and
Pi temperatures. Override the cell with `CV_BATTERY_MAH` (default 6000) /
`CV_BATTERY_FULL_V` (default 4.20) / `CV_BATTERY_LOW_V` (default 3.30).

## Firmware upload

`hardware/firmware_upload.py` copies the MicroPython sources to the ESP32 with
`mpremote`, writes `board_config.py` (`USE_MOCK`), and hard-resets the board so
`main.py` runs. Use `python dev.py upload-firmware [--mock] [--port PATH]`; the
backend also exposes a WebSocket `upload_firmware` command, which closes the
session, uploads, and re-boots it.

The serial port is auto-detected when `CV_ESP32_PORT` is unset: it prefers
CP210x/CH340/Espressif adapters by `/dev/serial/by-id`, then falls back to
`/dev/ttyUSB*`, then `/dev/ttyACM*`. This avoids opening an unrelated Arduino
or CDC device. Non-JSON MicroPython boot/REPL lines are skipped.

## AFE bring-up

[`AFE-GAIN-TEST.md`](AFE-GAIN-TEST.md) is a scope/DMM procedure for checking
the AD5933 excitation, Howland transconductance and INA gain before running the
two-reference calibration.

## Cautions

- **Mux logic levels:** the as-built CD74HC4067s run at **3.3 V**, so the ESP32
  address lines connect directly. If a mux is ever moved to 5 V, level-shift the
  address lines and check the analog signal swing against the mux rails.
- **Mux state at reset:** the muxes are always enabled, so before the firmware
  drives the address lines the selected electrodes are undefined. Keep the
  address lines pulled to a known level if boot-time state matters.
- **Frequency ceiling:** the AD5933 tops out near 100 kHz, so the
  research-recommended 300–500 kHz points are not reachable on this front end.
- **Safety:** battery-isolated operation only; never mains-connected with
  electrodes attached (see `docs/eit-bioimpedance/`).
