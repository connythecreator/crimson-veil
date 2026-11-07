# mp-firm

MicroPython firmware for the Crimson Veil ESP32 front end (AD5933 + 4× CD74HC4067 mux).

- `src/` — the firmware; transferred to the ESP32 directly.
- `base_fm/` — stock MicroPython ESP32 image.

`main.py` owns the global config (electrodes, frequency, I2C/mux pins,
telemetry), the scan process and the JSON protocol. The host sends
`{"type":"scan"}` and gets a frame of complex impedance points.

The real hardware is the parts-limited 8-electrode build: AD5933 at 3.3 V /
1 Vpp, a TL082 Howland on ±5 V biased at 2.5 V, an AD620 on ±5 V with REF at
1.65 V, and four 3.3 V CD74HC4067 muxes. The muxes are non-latching and always
enabled (`~E` tied low), and each role has its own 3-bit address bus. Firmware
sets each role independently and never drives an enable line. See
[`docs/eit-bioimpedance/README.md`](../../docs/eit-bioimpedance/README.md) for
the pin map.

## Files

- `src/main.py` — config + protocol loop + scan process + mux selection.
- `src/protocol.py` — line-delimited JSON wire format.
- `src/ad5933_driver.py` — AD5933 I2C driver.
- `src/mock_ad5933.py` — synthetic AD5933/mux back end for host bring-up.
- `src/status_led.py` — GPIO2 self-test failure LED (active-high, 5 Hz, 5 s).

## Wire protocol

host → esp: `{"type":"identify"}` · `{"type":"scan"}` (optional `"f":Hz`) · `{"type":"selftest"}` · `{"type":"mux_test"}` · `{"type":"stop"}`

esp → host: `hello` · `frame` · `telemetry` · `selftest_result` · `mux_test_result` · `error`

A failed `selftest` flashes GPIO2 at 5 Hz for five seconds. The pin is
active-high and driven low at boot.

## Build

```bash
.venv/bin/esptool --chip esp32 --port /dev/ttyUSB0 write-flash -z 0x1000 \
    base_fm/ESP32_GENERIC-20260824-v1.29.0.bin
.venv/bin/mpremote connect /dev/ttyUSB0 fs cp -r src :
.venv/bin/mpremote connect /dev/ttyUSB0 soft-reset
```

## Standalone bench test

`hwtest/` is a separate, self-contained firmware for bringing up the AD5933
analog channel with a known capacitor. Its analog test does not use the mux
bank, mock tables, pyEIT, the Raspberry Pi or the control service; the separate
`hwtest_mux` command runs the all-roles-per-electrode mux continuity cycle.
Its `--calibrate` mode
writes `cal.json` at multiple frequencies using a body-range resistor (default 100 Ω) and a 0.1 µF
capacitor; the main firmware combines them (resistor magnitude, capacitor phase),
loads the file at boot, and refuses scans (and fails the backend self-test) if it
is missing or invalid. See
[`hwtest/README.md`](hwtest/README.md).
