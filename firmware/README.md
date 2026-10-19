# firmware/ — ESP32 sketch (Arduino IDE)

Firmware for the ESP32 front-end controller. **You manage this** as a single
Arduino IDE sketch; it is not built by this repo.

The ESP32 is the primary interface between the hardware and the Python suite:

- owns the **hardware configuration** (AD5933 I²C, CD74HC4067 mux pin map, ring
  size) and reports its electrode count on boot, and
- runs a dedicated **single-shot** EIT acquisition routine: it measures exactly
  the plan the host sends and returns one frame. It does **not** loop —
  continuous scanning is implemented by the host.

It also reports **temperature** telemetry (its own die and the AD5933). Battery
state is owned by the Witty Pi BMS on the host, not by the ESP32.

## Protocol

The sketch must speak the line-delimited JSON protocol documented in
[`hardware/README.md`](../hardware/README.md) (and the module docstring in
[`hardware/esp32.py`](../hardware/esp32.py)). In short:

- On boot (and on `{"type":"identify"}`): send
  `{"type":"hello","firmware":…,"n_electrodes":…,"electrodes":[…],"sweep_hz":…}`.
- On `{"type":"scan"}`: run the fixed adjacent scan once, then send
  `{"type":"frame","points":[{"n":…,"f":…,"re":…,"im":…}, …]}` (one point per
  measurement, in pyEIT's standard adjacent order).
- Periodically: send `{"type":"telemetry","temp_esp32_c":…,"temp_ad5933_c":…}`.
- On `{"type":"selftest"}`: verify the AD5933 responds (temperature) and the mux
  bank can be addressed, then send
  `{"type":"selftest_result","firmware":…,"ad5933":bool,"mux":bool,"temp_ad5933_c":…,"error":…}`.
- On any fault: send `{"type":"error","message":…}`.

The host (`hardware/esp32.py`) is the reference implementation of the other
side of this protocol; matching it is the contract. The firmware owns the scan
process and calibration; the host sends no plan and applies no calibration.

## Uploading and mock mode

`python dev.py upload-firmware` (on the Pi, with `mpremote` installed) copies
the files in `firmware/mp-firm/src/` to the ESP32, writes `board_config.py`,
and hard-resets it so `main.py` runs. Pass `--mock` to make
`board_config.USE_MOCK = True`: the firmware then uses `mock_ad5933.py`
(FEM-generated tables for 4, 8 or 16 electrodes) instead of the unfinished
AD5933/mux path. `--electrodes N` sets `board_config.N_ELECTRODES`, which is
reported in `hello`; the mock tables and the kiosk electrode ring follow it.
`python dev.py mock-firmware` runs the same firmware under CPython on a pty.

`{"type":"mock_mode","mode":"baseline"|"target"|"continuous"|"auto"}` switches
the mock tables at runtime (mock mode only). The first full scan is the
baseline; in the default `continuous`/`auto` mode each later scan cycles through
eight anomaly positions, so monitor mode shows a moving anomaly. `target` forces
one static anomaly; `baseline` restarts the capture sequence.
