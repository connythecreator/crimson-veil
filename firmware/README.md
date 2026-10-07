# firmware/ — ESP32 sketch (Arduino IDE)

Firmware for the ESP32 front-end controller. **You manage this** as a single
Arduino IDE sketch; it is not built by this repo.

The ESP32 is the primary interface between the hardware and the Python suite:

- owns the **hardware configuration** (AD5933 I²C, CD74HC4067 mux pin map, ring
  size) and reports its electrode count on boot, and
- runs a dedicated **single-shot** EIT acquisition routine: it measures exactly
  the plan the host sends and returns one frame. It does **not** loop —
  continuous scanning is implemented by the host.

It also reports **battery** and **temperature** telemetry.

## Protocol

The sketch must speak the line-delimited JSON protocol documented in
[`hardware/README.md`](../hardware/README.md) (and the module docstring in
[`hardware/esp32.py`](../hardware/esp32.py)). In short:

- On boot (and on `{"type":"identify"}`): send
  `{"type":"hello","firmware":…,"n_electrodes":…,"electrodes":[…],"sweep_hz":…}`.
- On `{"type":"scan"}`: run the fixed adjacent scan once, then send
  `{"type":"frame","points":[{"n":…,"f":…,"re":…,"im":…}, …]}` (one point per
  measurement, in pyEIT's standard adjacent order).
- Periodically: send `{"type":"telemetry", …}` with battery/temperature.
- On any fault: send `{"type":"error","message":…}`.

The host (`hardware/esp32.py`) is the reference implementation of the other
side of this protocol; matching it is the contract. The firmware owns the scan
process and calibration; the host sends no plan and applies no calibration.
