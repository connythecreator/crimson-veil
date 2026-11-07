# AFE gain test — bench procedure

Checks the two gain stages separately, then the whole
AD5933 → Howland → electrode → AD620 → AD5933 chain on the **parts-limited
build**:

1. AD5933 excitation amplitude
2. Howland current-source transconductance
3. AD620 voltage gain
4. Overall receive chain with a known resistor/capacitor

Do this with **no electrodes and no patient**. Use an isolated/battery supply,
keep the injected current ≤1 mA peak, and discharge capacitors before touching
the fixture.

## As-built operating point

| Item | Value |
|---|---|
| AD5933 supply / range | 3.3 V, 1 Vpp |
| Howland op-amp | TL082, ±5 V, biased at 2.5 V |
| Howland current-set resistors | R8 = R13 = 5 kΩ (2×10 kΩ in parallel) |
| Howland bridge | 47 kΩ |
| AD620 supply | ±5 V |
| AD620 REF | 1.65 V (AD5933 VDD/2) |
| AD620 RG | trimmer ≈26 kΩ → G ≈ 2.9 |
| Mux bank | 4× CD74HC4067 at 3.3 V, `~E` tied low, `S3` tied low |

The AD5933 output is AC-coupled into the Howland, so the Howland input DC stays
at 2.5 V. The AD620 output is DC-coupled to the AD5933 VIN because both sit at
1.65 V. The muxes are always enabled; the firmware has no enable line.

## Equipment

- Oscilloscope, 2 channels (prefer differential or two probes with A−B math)
- DMM
- Precision resistors: 100 Ω, 1 kΩ (0.1% preferred)
- 0.1 µF capacitor
- Function generator (for the AD620 test)
- Bench supply / battery; the board's normal rails

## Preconditions

Measure these before applying a signal:

| Rail / node | Expected |
|---|---|
| +3.3 V, +5 V, −5 V | within 5% |
| Howland bias / input DC | 2.5 V ±0.1 V |
| AD620 REF | 1.65 V ±0.05 V |
| AD620 output with no signal | near 1.65 V, not at a rail |
| AD5933 VIN with no signal | near 1.65 V |

If the AD620 output sits at 0 V or a rail, fix power/reference before
continuing. A 2.5 V AD620 REF is wrong for the 3.3 V AD5933; it puts the output
0.85 V above VIN and injects DC current through the 10 kΩ input resistor.

## Test 0 — mux continuity

With only **electrode 0** wired to each mux and all other channels open:

```bash
python tools/mux_test.py --port /dev/ttyUSB0
```

The firmware sets Drive+ / Sense+ / Sense− and Drive− all to each electrode
(`--d-neg` omitted by default; the old C0/C1 short has been fixed). It reports
raw and calibrated impedance for each electrode. For this front end the sense
pair must follow the drive pair: **Sense+ on the same electrode as Drive+**, and
Sense− on the same electrode as Drive−. Reversing the sense pair is not a valid
measurement. Expected:

- electrode 0: `connected` with a finite impedance (the mux on-resistance plus
  the electrode-0 loop);
- electrodes 1–7: `open` (raw near zero);
- the current `cal.json` is used if valid and is never modified.

If electrode 0 is open, check the electrode-0 wiring and the mux address lines.
If another electrode is connected, its channel is not open (or the address bus
is miswired).

The production firmware `selftest` runs the same all-roles-per-electrode check
on every electrode and reports `mux: false` with the open electrodes named in
`error`. The service self-test turns that into an Impedance Subsystem failure.
A failed self-test flashes GPIO2 (active-high, low at boot) at 5 Hz for five
seconds.

## Test 1 — AD5933 excitation amplitude

Upload the current hwtest firmware, then leave the excitation on:

```bash
python tools/hwtest.py --upload --port /dev/ttyUSB0
python tools/hwtest.py --port /dev/ttyUSB0 --excite --f 10000
```

Connect a scope to **AD5933 VOUT**, AC-coupled. Measure peak-to-peak and
frequency. Expected at the as-built point:

| Range | AD5933 VDD | VOUT |
|---|---|---:|
| 1 V p-p | 3.3 V | ~0.97 V p-p |

The AD5933 VOUT has its own DC bias (about 0.76 V at this range/supply); the
input high-pass must remove it so the Howland input DC stays at 2.5 V. Verify
the DC level before measuring the AC amplitude.

Stop the excitation when finished:

```bash
python tools/hwtest.py --port /dev/ttyUSB0 --stop
```

If VOUT is zero while I²C and temperature work, check the AD5933 output
configuration/range and the VOUT pin/solder joint.

## Test 2 — Howland current-source transconductance

Connect a **1 kΩ 0.1%** resistor between `Drive+` and `Drive−`. Leave the
sense inputs disconnected or connected to the same nodes if your fixture is
Kelvin-wired. Keep the mux bank bypassed or addressed to the fixture; this test
is about the Howland, not the mux bank.

Start excitation at 10 kHz or 50 kHz (`--excite --f ...`). Measure:

- `V_in` — the Howland input (after the input high-pass)
- `V_RL` — the voltage across the 1 kΩ load, differentially

```
I_load = V_RL / R_L
Gm = I_load / V_in        [A/V]
```

### Expected transconductance

For the parts build (`bleed/sim/README.md`):

```
I_load = Vin * (1/Rs + 1/(4R)) / (1 + RL/(4R))
Rs = R8 = R13 = 5 kΩ
R  = 47 kΩ
```

With `Rs = 5 kΩ`, `R = 47 kΩ`, `RL = 1 kΩ`:

```
Gm ≈ 0.204 mA/V
```

At 1 V p-p at the Howland input that is ≈0.204 mA p-p and ≈0.204 V p-p across
a 1 kΩ load. The actual AD5933 VOUT is ~0.97 V p-p, so expect about
**0.20 mA p-p**. That is ~0.07 mA RMS, well below the 1 mA peak design ceiling.

### Current-source flatness

Repeat with `R_L` = 100 Ω, 1 kΩ and 10 kΩ at the same `V_in`. The current
should stay roughly constant:

- parts build: within about ±3% over 100 Ω–10 kΩ

A large drop at higher `R_L` means the current source is running out of
compliance or the input/power is wrong.

## Test 3 — AD620 voltage gain

Stop the AD5933 excitation. Disconnect the AD620 inputs from the drive/sense
nodes so you can inject a known differential signal.

Apply a **10 mV p-p, 10 kHz** differential signal across `Sense+`/`Sense−`,
with the common mode near the 2.5 V Howland bias. Use the function generator
through a divider if needed. Measure:

- `V_sense` — differential voltage directly at the AD620 input pins
- `V_INA` — AD620 output at the AD5933 VIN node

```
G = V_INA / V_sense
```

### Expected gain

Measure `Rg` with the power off, then:

| Device | Gain |
|---|---|
| AD620 | `G = 1 + 49.4 kΩ / Rg` |

The as-built trimmer is set to about **26 kΩ**, giving **G ≈ 2.9**. Useful
reference values:

| Rg | G |
|---:|---:|
| 49.4 kΩ | 2.0 |
| 26 kΩ | 2.9 |
| 12.35 kΩ | 5.0 |
| 5.49 kΩ | 10.0 |

Check:

- output offset is near REF (1.65 V)
- no clipping at the expected output swing
- gain is flat within a few percent from 1 kHz to 50 kHz
- `G` is within about ±5% of the calculated value

Note: a 1 kΩ load at high gain can drive the AD620 into its output limit. Use
a smaller load/current or a lower gain for the Howland test if the AD620 clips.

## Test 4 — overall chain and calibration

Reconnect the 0.1 µF capacitor fixture:

```
Drive+ ──┬──────────────┬── 0.1 uF ──┬──────────────┬── Drive−
         │              │            │              │
         └── Sense+ ────┘            └─── Sense− ───┘
```

Run the hwtest at 10 kHz and 50 kHz:

```bash
python tools/hwtest.py --port /dev/ttyUSB0 --f 10000
python tools/hwtest.py --port /dev/ttyUSB0 --f 50000
```

Expected:

- `signal` check passes (raw signal is hundreds/thousands of codes, not ~0)
- |Z| ≈ 159.15 Ω at 10 kHz, ≈31.83 Ω at 50 kHz
- phase ≈ −90°
- stability drift within the configured limits

Then calibrate both references:

```bash
# connect the 47-100 Ω resistor
python tools/hwtest.py --port /dev/ttyUSB0 --calibrate --fixture resistor --r-ohm 100 --freqs 10000,50000

# swap to the 0.1 uF capacitor
python tools/hwtest.py --port /dev/ttyUSB0 --calibrate --fixture capacitor --freqs 10000,50000
```

The main firmware loads both entries and combines them: resistor magnitude,
capacitor phase. Re-run both stages with the mux bank in the signal path before
trusting a full-ring scan; the mux on-resistance is part of the transfer
function.

## Fault isolation

| Symptom | Likely area |
|---|---|
| AD5933 VOUT = 0; I²C/temp pass | AD5933 output config/range or VOUT solder joint |
| VOUT good, drive voltage = 0 | Howland input/HPF, op-amp power, op-amp output |
| Drive voltage good, current = 0 | R8/R13, load/return, open drive path |
| Current good, sense voltage = 0 | Sense wiring, AD620 input path |
| Sense good, AD620 output = 0 | AD620 power, REF, Rg, AD620 output solder joint |
| AD620 output good, AD5933 raw ≈ 0 | AD5933 VIN/RFB, receive-path solder joint |
| Raw ≈ 0 with fixture connected | AFE unpowered, mux address wrong / mux not connected, or fixture not in the drive/sense loop |

The muxes are always enabled; if a role is on the wrong electrode, check its
S0–S2 wiring and the firmware address map, not an enable line.

## Record sheet

| Test | Frequency | Expected | Measured | Pass? | Notes |
|---|---:|---:|---:|---|---|
| VOUT | 10 kHz | ~0.97 V p-p | | | |
| Gm, 1 kΩ | 10 kHz | ~0.20 mA p-p | | | |
| Gm, 100 Ω | 10 kHz | ~0.20 mA p-p | | | |
| Gm, 10 kΩ | 10 kHz | ~0.20 mA p-p | | | |
| AD620 gain | 10 kHz | ~2.9 | | | |
| AD620 gain | 50 kHz | ~2.9 | | | |
| Overall \|Z\| | 10 kHz | 159.15 Ω | | | |
| Overall \|Z\| | 50 kHz | 31.83 Ω | | | |
