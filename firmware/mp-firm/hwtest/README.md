# hwtest — standalone AD5933 bench test

Self-contained firmware for bringing up the analog front end from a development
computer. It is **not** the production EIT firmware and does not use the
Raspberry Pi, the control service, pyEIT, the mux bank or any mock tables.

## What it tests

- ESP32 ↔ AD5933 I²C link (address `0x0D`)
- AD5933 temperature read
- Single-point AD5933 acquisition at 50 kHz (overridable)
- Drive/receive analog channel through a known capacitor
- Measurement stability and saturation
- Gain/phase calibration factor `K` for the known fixture
- Creates/merges `cal.json`, the calibration file consumed by the main firmware

It does **not** test the CD74HC4067 mux bank or electrode continuity.

## Bench I²C pins

| Signal | ESP32 pin | Dev-board label |
|---|---|---|
| SDA | GPIO21 | D21 |
| SCL | GPIO22 | D22 |

Bus 0 at **100 kHz**, AD5933 address `0x0D`, 10 kΩ pull-ups to 3.3 V on both
lines. This matches the production I²C pinout; the bench firmware simply does
not drive the mux outputs.

The driver uses the same I²C behavior as the working
[`mjmeli/arduino-ad5933`](https://github.com/mjmeli/arduino-ad5933) library:

- each register byte is written in its own 2-byte transaction
- reads use the AD5933 address-pointer register (`0xB0`)
- the control register is read/modify/written so range and PGA bits survive

This avoids the multi-byte `writeto_mem`/`readfrom_mem` transfers that fail on
the raw chip.

## Fixture

```
Drive+ ──┬──────────────┬── 0.1 uF ──┬──────────────┬── Drive−
         │              │            │              │
         └── Sense+ ────┘            └─── Sense− ───┘
```

- Fit a **0.1 µF** capacitor between `Drive+` and `Drive−`.
- Strap `Sense+` to `Drive+` and `Sense−` to `Drive−` at the capacitor.
- Keep the leads short. Do not connect electrodes or a patient.
- Power the board from an isolated battery/USB supply.

Expected impedance `Z = 1 / (j·2πfC)`:

| Frequency | \|Z\| | Phase |
|---:|---:|---:|
| 1 kHz | 1591.5 Ω | −90° |
| 5 kHz | 318.3 Ω | −90° |
| 10 kHz | 159.2 Ω | −90° |
| 50 kHz | **31.83 Ω** | −90° |

At 50 kHz the impedance is only ~32 Ω. If the reading is noisy, clipped, or
saturated, run at 5–10 kHz with `--f`.

## Upload from this computer

The ESP32 is connected directly to this machine. Install `pyserial` and
`mpremote` in the local venv, then:

```bash
python tools/hwtest.py --upload --port /dev/ttyUSB0
```

`--port` is optional when exactly one `/dev/ttyACM*` or `/dev/ttyUSB*` is
present. If an Arduino or another USB serial device is also connected, pass the
ESP32's port explicitly (the ESP32 is usually the CP2102/CH340 `/dev/ttyUSB*`;
the host tool also prefers those by USB ID). This copies only:

```
main.py
hwtest_core.py
ad5933_driver.py
```

The production firmware in `../src/` uses the same repaired driver and loads
the `cal.json` this firmware writes. Re-upload the production firmware when the
bench test is finished; `cal.json` stays on the ESP32 across uploads.

## Run

```bash
python tools/hwtest.py --port /dev/ttyUSB0
python tools/hwtest.py --port /dev/ttyUSB0 --f 10000
python tools/hwtest.py --port /dev/ttyUSB0 --calibrate --freqs 10000,50000
python tools/hwtest.py --port /dev/ttyUSB0 --json
```

The firmware auto-runs once on boot (50 kHz, 16 samples) and then accepts
commands over USB serial. It discards one warm-up point before collecting the
samples, then calibrates from the first half and verifies on the second half.
The host tool sends its own `hwtest_run` and ignores the boot result.

`--calibrate` measures each frequency in `--freqs`, merges the resulting `K`
entries with any existing `cal.json`, and writes the file back to the ESP32.
The file is what the main EIT firmware loads at boot.

Exit codes: `0` pass/warn, `1` fail, `2` link/protocol error.

## Serial protocol

Host → ESP32:

```json
{"type":"hwtest_run","seq":1,"f":50000,"c_f":1e-7,"samples":16,"tol_pct":5,"tol_deg":5}
{"type":"hwtest_calibrate","seq":1,"freqs":[10000,50000],"c_f":1e-7,"samples":16}
{"type":"hwtest_identify"}
{"type":"hwtest_temp"}
{"type":"hwtest_stop"}
```

ESP32 → host:

```json
{"type":"hwtest_hello","firmware":"hwtest 1.2.0","fixture":{"kind":"capacitor","c_f":1e-7},"default_f":50000,"calibration":{"present":false,"entries":0,"error":"..."}}
{"type":"hwtest_result","seq":1,"status":"pass","temp_ad5933_c":30.0,"checks":[],"raw":{},"calibration":{},"measured":{}}
{"type":"hwtest_calibration","seq":1,"file":"cal.json","entries":[{"f":10000,"k_re":1,"k_im":0,"status":"pass"}],"status":"pass","error":null}
{"type":"hwtest_temp","temp_ad5933_c":30.0}
{"type":"hwtest_error","message":"..."}
```

## Calibration math

For raw AD5933 complex data `S` and known fixture impedance `Z_expected`:

```
K = Z_expected · S_cal
Z_measured = K / S_verify
```

The first half of the samples derives `K`; the second half verifies it. `K` is
complex, so this corrects both magnitude and phase against the capacitor's
known `31.83 Ω @ −90°` reference. This makes the check sensitive to drift and
instability. It does not prove absolute traceable accuracy: the same capacitor
is the reference. A second known component or a DMM is needed for that.

## Calibration file (`cal.json`)

`--calibrate` writes a JSON file on the ESP32 filesystem:

```json
{
  "version": 1,
  "fixture": {"kind": "capacitor", "c_f": 1e-7},
  "entries": [
    {"f": 10000.0, "k_re": ..., "k_im": ..., "mag": ..., "phase_deg": ..., "status": "pass"}
  ]
}
```

The main firmware loads this at boot, selects the nearest frequency for a scan,
and applies `Z = K / raw`. If the file is missing, empty, or invalid, the main
firmware refuses scans and reports `calibration: false` in its selftest so the
backend self-test fails with the calibration error. Re-run `--calibrate` after
changing the fixture or analog front end.

## Troubleshooting

- **`i2c` passes but acquisition fails with `OSError: [Errno 19] ENODEV`**:
  the address is visible on the bus but the AD5933 is not acknowledging a
  write. Check that the module has a common GND, that SDA→GPIO21 and
  SCL→GPIO22 are not swapped, that both lines have 10 kΩ pull-ups, and that no
  other I2C master shares the bus.
- **5 V AD5933 through a logic-level shifter**: an AD5933 may run at 5 V
  (2.7–5.5 V), but the ESP32 side must be 3.3 V. The 5 V supply and the ESP32
  **must share a ground**; "5 V only" is not enough. The shifter must have
  **HV = 5 V** (the same rail as the AD5933) and **LV = 3.3 V**, with the
  AD5933-side pull-ups to 5 V and the ESP32-side pull-ups to 3.3 V. If the
  shifter's high side is only 3.3 V while the AD5933 runs at 5 V, the AD5933
  sees ~3.3 V as a logic high, which is below its VIH (≈0.7 × 5 V = 3.5 V):
  scans and reads can work while writes NACK. Use a bidirectional I2C shifter
  (BSS138 or PCA9306 class); a unidirectional shifter or a TXS0108E with the
  wrong loading can fail the same way. Never let 5 V reach an ESP32 pin.
- **Temperature unavailable / acquisition fails at every frequency**: the
  same bus problem. The I²C bus runs at 100 kHz; try a different excitation
  frequency with `--f` only after the raw acquisition works.
- **50 kHz reading is noisy or clipped**: use `--f 10000` or `--f 5000`.

## Caveats

- The AD5933 `measure()` sequence here is bench bring-up. Verify the raw values
  against a scope/DMM before trusting `K`.
- Power rails still need a DMM check; this firmware cannot see them.
- The production firmware now uses the same byte-wise/`0xB0` driver and loads
  `cal.json`; keep the two driver copies in sync if the protocol changes.
- Reflashing the MicroPython base image erases `cal.json`; recalibrate with
  `--calibrate` afterward.
- Safety: ≤1 mA injected current, battery/isolated supply only, no human or
  animal testing.
