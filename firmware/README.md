# firmware/ — ESP32 front end

The production firmware is **MicroPython** in [`mp-firm/src/`](mp-firm/src/).
It is not an Arduino sketch and is not built by this repo. The ESP32 is the
primary interface between the analog front end and the Python suite:

- owns the **hardware configuration** (AD5933 I²C, CD74HC4067 mux pin map, ring
  size) and reports its electrode count on boot;
- runs a **single-shot** EIT acquisition: the fixed adjacent drive/sense
  sequence once per `scan` command, returning one frame. Continuous scanning is
  the host's policy;
- loads and applies the gain/phase calibration in `cal.json`;
- reports its own die temperature and the AD5933's.

Battery state is owned by the Witty Pi BMS on the host, not by the ESP32.

## As-built front end

- AD5933 at **3.3 V**, **1 Vpp** excitation.
- Mirrored Howland (TL082, ±5 V) biased at **2.5 V**.
- AD620 on ±5 V, REF at **1.65 V** (AD5933 VDD/2), RG trimmer ≈26 kΩ (G ≈ 2.9).
- Four CD74HC4067 muxes at **3.3 V**, `~E` tied low, `S3` tied low, non-latching,
  with **independent** 3-bit address buses. Firmware never uses an enable line.

The mux map and the electrical details are in
[`docs/eit-bioimpedance/README.md`](../docs/eit-bioimpedance/README.md).

## Protocol

The firmware speaks the line-delimited JSON protocol documented in
[`hardware/README.md`](../hardware/README.md) and implemented on the host side
by [`hardware/esp32.py`](../hardware/esp32.py):

- On boot and on `{"type":"identify"}`: send
  `{"type":"hello","firmware":…,"n_electrodes":…,"electrodes":[…],"sweep_hz":…}`.
- On `{"type":"scan"}`: run the fixed adjacent scan once, then send
  `{"type":"frame","points":[{"n":…,"f":…,"re":…,"im":…}, …]}`.
- Periodically: send `{"type":"telemetry","temp_esp32_c":…,"temp_ad5933_c":…}`.
- On `{"type":"selftest"}`: verify the AD5933 responds (temperature), run the
  mux continuity check (all four roles on each electrode), verify calibration,
  then send `selftest_result`. An open electrode sets `mux: false` and is named
  in `error`; the service self-test then fails the Impedance Subsystem check.
- On `{"type":"mux_test"}`: set every electrode on all four roles and report the
  loop impedance in `mux_test_result`. This is the bench check for a mux bank
  with only electrode 0 wired; `tools/mux_test.py` runs it over serial.
- On any fault: send `{"type":"error","message":…}`.

A failed self-test flashes the **GPIO2 status LED** (active-high, driven low at
boot) at 5 Hz for five seconds. The LED is off unless a self-test has just
failed; a later passing self-test cancels the flash.

## Uploading and mock mode

```bash
python dev.py upload-firmware --mock   # synthetic AD5933/mux tables
python dev.py upload-firmware          # real front end
python dev.py mock-firmware            # run the firmware on a local pty
```

The uploader copies `firmware/mp-firm/src/` to the ESP32 with `mpremote`,
writes `board_config.py`, and hard-resets the board. `--mock` selects the
synthetic tables (`mock_ad5933.py`, `mock_tables_{4,8,16}.py`); `--electrodes N`
sets `board_config.N_ELECTRODES`. The real 3-bit mux map supports 4 or 8
electrodes; the mock tables also cover 16. The mock tables are post-calibration
boundary voltages, so the firmware bypasses `Z = K / S` for the mock driver
(`is_mock`); applying it would invert the difference image.

`{"type":"mock_mode","mode":"baseline"|"target"|"continuous"|"auto"}` switches
the mock tables at runtime (mock mode only).

## Standalone bench firmware

- [`mp-firm/hwtest/`](mp-firm/hwtest/) — ESP32 MicroPython bench firmware for
  the AD5933 and the analog channel with a known-capacitor/resistor fixture. It
  does **not** use the mux bank, mock tables, pyEIT or the Pi. Its
  `--calibrate` mode writes `cal.json` from a body-range resistor (default
  100 Ω) and a 0.1 µF capacitor; the production firmware combines them.
- [`cpp-firm/ad5933_test/`](cpp-firm/ad5933_test/) — a separate
  Arduino-framework sketch for manual AD5933 bring-up. It prints sample-style
  `R/I/|Z|` lines over Serial and is not the production firmware.

The production firmware refuses scans when `cal.json` is missing or invalid,
and `selftest_result` reports `calibration: false` with the error.
