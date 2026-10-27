# ad5933_test — capacitor bench test

Arduino-framework sketch based on the `ad5933-test` example from
[`mjmeli/arduino-ad5933`](https://github.com/mjmeli/arduino-ad5933). It uses
the installed library in `~/Arduino/libraries/arduino-ad5933` and prints
sample-style `R/I/|Z|` lines over Serial.

## Wiring

| Signal | ESP32 pin |
|---|---|
| SDA | GPIO21 |
| SCL | GPIO22 |

- Power the AD5933 at **3.3 V** and connect SDA/SCL directly.
- 10 kΩ pull-ups to 3.3 V.
- Fixture: **0.1 µF** between `Drive+` and `Drive−`; `Sense+` strapped to
  `Drive+`, `Sense−` strapped to `Drive−`.

## Library patches

The installed library has two local patches. They are outside this repo and
must be reapplied if the library is reinstalled:

1. `AD5933.cpp`: `#include <Math.h>` → `#include <math.h>` (Linux is
   case-sensitive).
2. `AD5933::frequencySweep()`: measure exactly `n` points instead of looping on
   `STATUS_SWEEP_DONE`. The upstream loop returns false for a single-point
   (`n == 1`) sweep, which made calibration fail and produced `|Z|=inf`.

## Run

1. Upload with the Arduino IDE (ESP32 Dev Module).
2. Open Serial Monitor at **115200**.
3. Expect:

```
AD5933 Test Started!
Calibrated!
50: R=.../I=...  |Z|=32.00
```

`REF_IMPEDANCE_OHM` is `32` because the library takes an integer reference;
the ideal 0.1 µF value at 50 kHz is 31.83 Ω. For a larger, less noisy signal,
change `START_FREQ` to `10000` and `REF_IMPEDANCE_OHM` to `159`.

The library does not calibrate phase; only raw I/Q and calibrated magnitude are
reported.
