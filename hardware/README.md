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
  `n_electrodes`, the electrode list, and the firmware version. The **ESP32 owns
  the hardware configuration** (pin maps, mux wiring, ring size); the host never
  hardcodes it.
- **`identify`** — `esp32:/dev/ttyACM0` (or whatever port is configured).
- **`measure`** — sends the **host-owned scan plan** (the full per-measurement
  list of drive/sense pairs and frequencies) and returns one `RawPoint` per
  entry. The ESP32 executes **single-shot** scans only; continuous mode is a
  host concern and lives in `service/`.
- **`telemetry`** — returns the most recent battery/temperature reading the
  ESP32 has pushed (used by the kiosk status bar, with a sysfs fallback).

The `CalibrationTable` in `software/acquisition/calibration.py` is applied on
the host, so the ESP32 returns raw complex impedance.

## Wire protocol (USB CDC, line-delimited JSON)

One JSON object per line. See the module docstring in `esp32.py` for the
authoritative description; the firmware (Arduino IDE) must match it.

| host → ESP32 | purpose |
|---|---|
| `{"type":"identify"}` | ask the ESP32 to (re-)announce itself |
| `{"type":"scan","plan":[{"f":Hz,"d":[a,b],"s":[c,d]}, …]}` | execute one single-shot scan |
| `{"type":"stop"}` | abort / release |

| ESP32 → host | purpose |
|---|---|
| `{"type":"hello","firmware":str,"n_electrodes":int,"electrodes":[…],"sweep_hz":float}` | sent unsolicited on boot, and in reply to `identify` |
| `{"type":"frame","points":[{"f":Hz,"re":float,"im":float}, …]}` | one frame, one point per plan entry, in order |
| `{"type":"telemetry","battery_pct":float\|null,"battery_charging":bool,"temp_c":float\|null}` | periodic battery/temperature |
| `{"type":"error","message":str}` | a fault the host should surface |

## Configuration

| env | default | meaning |
|---|---|---|
| `CV_BACKEND` | `sim` | set to `esp32` to use this backend |
| `CV_ESP32_PORT` | `/dev/ttyACM0` | USB serial device |
| `CV_ESP32_BAUD` | `115200` | serial baud |

Install the device dependency with `requirements-pi.txt` (`pyserial`). The
service account needs access to the serial device (add it to the `dialout`
group).

## Cautions

- **Logic levels:** a CD74HC4067 powered at 5 V wants V_IH ≈ 3.5 V. Run the mux
  at 3.3 V or level-shift.
- **Frequency ceiling:** the AD5933 tops out near 100 kHz, so the
  research-recommended 300–500 kHz points are not reachable on this front end.
- **Safety:** battery-isolated operation only; never mains-connected with
  electrodes attached (see `docs/eit-bioimpedance/`).
