# hwtest — standalone AD5933 bench test

Self-contained firmware for bringing up the analog front end from a development
computer. It is **not** the production EIT firmware and does not use the
Raspberry Pi, the control service, pyEIT or any mock tables. The analog test
bypasses the mux bank; a separate `hwtest_mux` command runs the mux continuity
cycle.

## What it tests

- ESP32 ↔ AD5933 I²C link (address `0x0D`)
- AD5933 temperature read
- Single-point AD5933 acquisition at 50 kHz (overridable)
- Drive/receive analog channel through a known capacitor
- Measurement stability and saturation
- Gain/phase calibration factor `K` for a body-range resistor (default 100 Ω) or a 0.1 µF capacitor
- Creates/merges `cal.json`, the calibration file consumed by the main firmware

The analog test does **not** exercise the CD74HC4067 mux bank. `hwtest_mux`
does: it sets all four roles to each electrode and reports connected/open.

## Bench I²C pins

| Signal | ESP32 pin | Dev-board label |
|---|---|---|
| SDA | GPIO21 | D21 |
| SCL | GPIO22 | D22 |

Bus 0 at **100 kHz**, AD5933 address `0x0D`, 10 kΩ pull-ups to 3.3 V on both
lines. This matches the production I²C pinout. The analog test does not drive
the mux outputs; `hwtest_mux` drives the production mux pin map. The as-built
AD5933 runs at **3.3 V**, so the I²C
lines connect directly with no level shifter.

The as-built analog chain around it is a TL082 Howland on ±5 V biased at 2.5 V,
an AD620 on ±5 V with REF at **1.65 V** (AD5933 VDD/2), and an RG trimmer set
to about **26 kΩ** (G ≈ 2.9).

A failed `hwtest_run`, `hwtest_calibration` or `hwtest_mux` flashes GPIO2
(active-high, driven low at boot) at 5 Hz for five seconds. A passing result
cancels the flash.

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
python tools/hwtest.py --port /dev/ttyUSB0 --range 1vpp --samples 32 --f 50000
python tools/hwtest.py --port /dev/ttyUSB0 --calibrate --fixture resistor --range 1vpp --samples 32 --freqs 10000,50000
python tools/hwtest.py --port /dev/ttyUSB0 --calibrate --fixture capacitor --range 1vpp --samples 32 --freqs 10000,50000
python tools/hwtest.py --port /dev/ttyUSB0 --json
python tools/hwtest.py --port /dev/ttyUSB0 --mux
```

The production firmware now runs the AD5933 in the **1 Vpp** range at **3.3 V**.
At 50 kHz with the 0.1 µF fixture, 16 samples can be marginal (the signal is
~500 codes); use `--samples 32` for a stable 1 Vpp calibration. The Howland
input remains biased at 2.5 V; the AD5933 output is AC-coupled into it. The
AD620 output is DC-coupled to the AD5933 VIN because both sit at 1.65 V.

The firmware announces `hwtest_hello` on boot and then waits for commands; the
host tool sends `hwtest_run`. It discards one warm-up point before collecting
the samples, then calibrates from the first half and verifies on the second
half.

`--calibrate` measures each frequency in `--freqs` for the selected
`--fixture` (`resistor` or `capacitor`), merges the resulting `K` entries with
any existing `cal.json`, and writes the file back to the ESP32. The two stages
are explicit:

1. Connect a **body-range resistor** (the default is **100 Ω**; use a 0.1% part) and run `--fixture resistor`.
2. Swap to the **0.1 µF capacitor** and run `--fixture capacitor`.

The main firmware combines them: magnitude from the resistor, phase from the
capacitor. Do not use a 10 kΩ reference at the normal 1 Vpp operating point;
it is outside the linear range and will be rejected. The hwtest result also prints the magnitude/phase difference between
the two references at each frequency.

Exit codes: `0` pass/warn, `1` fail, `2` link/protocol error.

## Serial protocol

Host → ESP32:

```json
{"type":"hwtest_run","seq":1,"f":50000,"fixture":"capacitor","c_f":1e-7,"r_ohm":100,"samples":16}
{"type":"hwtest_calibrate","seq":1,"freqs":[10000,50000],"fixture":"resistor","r_ohm":100,"c_f":1e-7,"samples":16}
{"type":"hwtest_mux","seq":1,"f":50000,"min_raw":10}
{"type":"hwtest_identify"}
{"type":"hwtest_temp"}
{"type":"hwtest_stop"}
```

ESP32 → host:

```json
{"type":"hwtest_hello","firmware":"hwtest 1.3.0","fixture":{"kind":"capacitor","c_f":1e-7,"r_ohm":100},"default_f":50000,"calibration":{"present":false,"entries":0,"error":"..."}}
{"type":"hwtest_result","seq":1,"status":"pass","temp_ad5933_c":30.0,"checks":[],"raw":{},"calibration":{},"measured":{}}
{"type":"hwtest_calibration","seq":1,"file":"cal.json","fixture":"resistor","entries":[{"f":10000,"fixture":"resistor","r_ohm":100,"k_re":1,"k_im":0,"status":"pass"}],"comparison":[],"status":"pass","error":null}
{"type":"hwtest_mux_result","seq":1,"f_hz":50000,"min_raw":10,"status":"pass","open_electrodes":[],"points":[{"e":0,"raw_abs":125.0,"status":"connected"}]}
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
  "version": 2,
  "entries": [
    {"f": 10000.0, "fixture": "resistor", "r_ohm": 100,
     "k_re": ..., "k_im": ..., "mag": ..., "phase_deg": ..., "status": "pass"},
    {"f": 10000.0, "fixture": "capacitor", "c_f": 1e-7,
     "k_re": ..., "k_im": ..., "mag": ..., "phase_deg": ..., "status": "pass"}
  ]
}
```

The main firmware loads this at boot, selects the nearest frequency for a scan,
and combines the two references into one `K`: `|K|` from the resistor and
`arg(K)` from the capacitor. It then applies `Z = K / raw`. The two references
must agree (default tolerance 10% magnitude / 5 degrees phase); if they do not,
the calibration is rejected and scans/selftest fail. A 10 kΩ resistor is too
high for the current front end at 1 Vpp excitation; use a 100–470 Ω reference
or reduce the excitation/gain and recalibrate both stages.
If the file is missing, empty, or invalid, scans are refused and the backend
self-test fails with the calibration error. Re-run both calibration stages
after changing the fixture, mux bank or analog front end.

## Troubleshooting

- **`i2c` passes but acquisition fails with `OSError: [Errno 19] ENODEV`**:
  the address is visible on the bus but the AD5933 is not acknowledging a
  write. Check that the module has a common GND, that SDA→GPIO21 and
  SCL→GPIO22 are not swapped, that both lines have 10 kΩ pull-ups, and that no
  other I2C master shares the bus.
- **Temperature unavailable / acquisition fails at every frequency**: the
  same bus problem. The I²C bus runs at 100 kHz; try a different excitation
  frequency with `--f` only after the raw acquisition works.
- **Raw ≈ 0 with fixture connected**: the fixture is not in the drive/sense
  loop, the AFE is unpowered, or the AD620 REF/RG is wrong. The analog test
  does not drive the mux bank; keep any mux bank bypassed or addressed to the
  fixture. Use `--mux` to test the mux bank separately.
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
