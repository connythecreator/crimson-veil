# hardware/ — ESP32 hardware backend

The physical front end (AD5933 + CD74HC4067 mux bank) is driven by an **ESP32**.
It is the primary interface between the hardware and the Python suite, wired to
the host over **USB serial**.

```
ESP32  ──USB serial (115200)──  Python host (service/)
  │  AD5933 (I²C)                     hardware/esp32.py
  │  4× CD74HC4067 mux               software.pipeline
```

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
| `{"type":"selftest"}` | verify the AD5933 + mux and report `selftest_result` |
| `{"type":"stop"}` | abort / release |

| ESP32 → host | purpose |
|---|---|
| `{"type":"hello","firmware":str,"n_electrodes":int,"electrodes":[…],"sweep_hz":float}` | sent unsolicited on boot, and in reply to `identify` |
| `{"type":"frame","points":[{"n":int,"f":Hz,"re":float,"im":float}, …]}` | one frame, the firmware's adjacent sequence, `n` = index in that sequence |
| `{"type":"telemetry","temp_esp32_c":float\|null,"temp_ad5933_c":float\|null}` | periodic on-chip temperatures |
| `{"type":"selftest_result","firmware":str,"ad5933":bool,"mux":bool,"temp_ad5933_c":float\|null,"error":str\|null}` | reply to `selftest` |
| `{"type":"error","message":str}` | a fault the host should surface |

## Configuration

| env | default | meaning |
|---|---|---|
| `CV_BACKEND` | `sim` | set to `esp32` to use this backend |
| `CV_ESP32_PORT` | `/dev/ttyACM0` | USB serial device |
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
{ ts, power_mode (0=USB, else battery), vin_v, vout_v (5 V rail), iout_a,
  temp_c (LM75B), charging, standby, low_v }
```

`service/metrics.py` reads it, estimates **state-of-charge** and **runtime**
from voltage + draw (anchored at `low_v` = 0 %), and merges in the ESP32 and
Pi temperatures. Override the cell with `CV_BATTERY_MAH` (default 6000) /
`CV_BATTERY_FULL_V` (default 4.20) / `CV_BATTERY_LOW_V` (default 3.30).

## Cautions

- **Logic levels:** a CD74HC4067 powered at 5 V wants V_IH ≈ 3.5 V. Run the mux
  at 3.3 V or level-shift.
- **Frequency ceiling:** the AD5933 tops out near 100 kHz, so the
  research-recommended 300–500 kHz points are not reachable on this front end.
- **Safety:** battery-isolated operation only; never mains-connected with
  electrodes attached (see `docs/eit-bioimpedance/`).
