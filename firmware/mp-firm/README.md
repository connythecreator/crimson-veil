# mp-firm

MicroPython firmware for the Crimson Veil ESP32 front end (AD5933 + 4× CD74HC4067 mux).

- `src/` — the firmware; transferred to the ESP32 directly.
- `base_fm/` — stock MicroPython ESP32 image.

`main.py` owns the global config (electrodes, frequency, I2C/mux pins, telemetry), the scan process and the JSON protocol. The host sends `{"type":"scan"}` and gets a frame of complex impedance points.

## Files

- `src/main.py` — config + protocol loop + scan process + mux selection.
- `src/protocol.py` — line-delimited JSON wire format.
- `src/ad5933_driver.py` — AD5933 I2C driver.

## Wire protocol

host → esp: `{"type":"identify"}` · `{"type":"scan"}` (optional `"f":Hz`) · `{"type":"stop"}`

esp → host: `hello` · `frame` · `telemetry` · `error`

## Build

```bash
.venv/bin/esptool --chip esp32 --port /dev/ttyUSB0 write-flash -z 0x1000 \
    base_fm/ESP32_GENERIC-20260824-v1.29.0.bin
.venv/bin/mpremote connect /dev/ttyUSB0 fs cp -r src :
.venv/bin/mpremote connect /dev/ttyUSB0 soft-reset
```
