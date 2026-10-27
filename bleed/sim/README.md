# Mirrored Howland current pump — LTspice test bench

Simulation of the excitation stage in `../bleed.kicad_sch` (U5A/U5B, TL082ACP,
±5 V). The topology is taken from the KiCad schematic, not from
`docs/eit-bioimpedance/eit-netlist.md`.

## Topology (from the schematic)

```
U5A:  CurrentOut --R6(47k)-- -In A
      U5A out --R7(47k)-- -In A
      Drive+   --R9(47k)-- +In A --R10(47k)-- Earth
      U5A out --R8(Rs)-- C3(0.1u) -- Drive+

U5B:  U5B out --R12(47k)-- -In B --R11(47k)-- Earth
      Drive-   --R14(47k)-- +In B --R15(47k)-- CurrentOut
      U5B out --R13(Rs)-- C2(0.1u) -- Drive-

Load: Drive+ --RL-- Drive-
```

* **R8 and R13 are the current-setting resistors**, not the 47k network.
* The external load (electrodes / body model, `RL`) sits between `Drive+` and
  `Drive-`; the two pumps drive it differentially.
* `C2`/`C3` (0.1 µF) AC-couple the two outputs.

For R6 = R7 = R9 = R10 = R11 = R12 = R14 = R15 = R, and R8 = R13 = Rs:

```
I_load = Vin · (1/Rs + 1/(4R)) / (1 + RL/(4R))
```

The `1/(4R)` term is current stolen by the 47k feedback dividers. It is
negligible when Rs ≪ R and a **24 % error when Rs = R = 47k** — which is why
the all-47k build does not hit the intended current.

## Results

All runs: TL082 (ADI `ADTL082` macromodel), ±5 V, 50 kHz, RL = 1 kΩ unless noted.

### As drawn — every resistor 47k, 1 V p-p input

| Quantity | Value |
|---|---|
| `I(R8)`, `I(R13)` | 21.3 µA p-p (= Vin/47k) |
| Load current | **26.5 µA p-p** |
| Load voltage | 26.5 mV p-p |

Not 1 mA. The extra 5.2 µA is the feedback-divider current.

### Sweep of R8/R13 (1 V p-p input, 1 kΩ load)

| R8 = R13 | Load current |
|---|---|
| 47k | 26.5 µA p-p |
| 22k | 50.6 µA p-p |
| 10k | 104.9 µA p-p |
| 4.7k | 217.3 µA p-p |
| 2.2k | 458.4 µA p-p |
| **1k** | **1.002 mA p-p** |

### Current-source behaviour (R8 = R13 = 1k, 1 V p-p input)

| RL | Load current |
|---|---|
| 100 Ω | 1.006 mA p-p |
| 470 Ω | 1.005 mA p-p |
| 1 kΩ | 1.002 mA p-p |
| 2.2 kΩ | 0.997 mA p-p |
| 4.7 kΩ | 0.985 mA p-p |
| 10 kΩ | 0.958 mA p-p |

±2.5 % over a 100:1 load range; output impedance ≈ **197 kΩ** at 50 kHz
(theoretical 4R ≈ 188 kΩ).

### DC bias of the AD5933 VOUT (R8 = R13 = 1k, 1 V p-p, 1 kΩ)

| VOUT bias | Load current | U5B output range |
|---|---|---|
| 0 V | 1.0018 mA p-p | −0.82 … +0.82 V |
| 1.65 V | 1.0018 mA p-p | +1.66 … +3.30 V |
| 2.5 V | 0.9805 mA p-p | +3.58 … +3.87 V — at the rail |

The input is DC-coupled, so the VOUT bias propagates to the op-amp outputs
(unequally: U5A sits at about −0.5·Vbias, U5B at about +1.5·Vbias).

The AD5933's actual VOUT bias is **not always VDD/2** — it is set by the
selected excitation range and scales ratiometrically with VDD:

| Range | At VDD = 3.3 V | At VDD = 5.0 V |
|---|---|---|
| 2000 mV p-p | 1.98 V p-p, 1.48 V bias | 3.00 V p-p, 2.24 V bias |
| 1000 mV p-p | 0.97 V p-p, 0.76 V bias | 1.47 V p-p, 1.15 V bias |
| 400 mV p-p | 0.38 V p-p, 0.31 V bias | 0.58 V p-p, 0.47 V bias |
| 200 mV p-p | 0.20 V p-p, 0.17 V bias | 0.30 V p-p, 0.24 V bias |

(Values are the datasheet/AN-847 figures scaled by VDD/3.3.)

### 5 V AD5933 operation

The AD5933 is specified for **VDD = 2.7 … 5.5 V** (absolute max 7 V), so
running it at 5 V is legitimate — the ±5 V TL082 rails and the 5 V AD5933 are
not a problem. What changes is the excitation amplitude and bias, which scale
with VDD. Simulated at the reference design's 1000 mV p-p range setting:

| VDD / range | VOUT | Load current (Rs = 1k) | U5B range |
|---|---|---|---|
| 3.3 V, 1000 mV p-p | 0.97 V p-p, 0.76 V bias | 0.99 mA p-p | ≈ 0.3 … 1.9 V |
| 5.0 V, 1000 mV p-p | 1.47 V p-p, 1.15 V bias | 1.47 mA p-p | 0.52 … 2.94 V |
| 5.0 V, 2000 mV p-p | 3.00 V p-p, 2.24 V bias | 2.56 mA p-p | 2.05 … 3.91 V — clipping |

At 5 V the 2000 mV setting drives U5B into the rail; the 1000 mV setting is
comfortable. With the input HPF fitted, the 2000 mV case recovers: outputs
swing ±2.10 V / ±2.47 V and the load current is 3.0 mA p-p, so use Rs ≈ 3k
for 1 mA p-p. Note that at 5 V the same range gives ~1.5× the current, so
Rs = 1k produces 1.47 mA p-p, not 1.0 mA. Use Rs ≈ 1.5k for 1 mA p-p at 5 V,
or run the AD5933 at 3.3 V to match the reference design's 1 mA.

### 1 mA **peak** operating point

2 V p-p excitation, R8 = R13 = 1k, VOUT bias 1.65 V:
**1.991 mA p-p = 0.996 mA peak**, U5B output 1.01 … 3.66 V (no clipping).

### Removing the VOUT DC offset

Two ways to keep the bias out of the pump. Both were simulated at
R8 = R13 = 1k, 2 V p-p, 1 kΩ load.

**A. AC-couple the input** (`howland_accouple.cir`): series cap between
`CurrentOut` and the R6/R15 junction, plus a DC return resistor from that
junction to ground. Without the return resistor the junction floats at DC
and the pump has no defined operating point — the cap alone is not enough.

This is what the reference design does: its AD5933 front end has a first-order
HPF (100 kΩ + 10 nF, corner ≈ 160 Hz) between VOUT and the Howland, plus the
0.1 µF caps in the output legs. Size the HPF for the lowest excitation
frequency you need (10 nF is only good down to ~1 kHz).

| Quantity | Value |
|---|---|
| Load current | 2.0035 mA p-p (unchanged) |
| `V(A_OUT)` | ±1.399 V (centred on 0) |
| `V(B_OUT)` | ±1.647 V (centred on 0) |

Centring on 0 gives the most symmetric headroom at ±5 V. With
`C = 1 µF` and `R_bias = 470k`, the high-pass corner is ≈ 3.4 Hz
(`47k ∥ 470k` with C) and the DC settling constant `C·R_bias` ≈ 0.47 s.
Use a film/C0G cap, not an electrolytic, at low excitation frequencies.

**B. Re-bias the feedback dividers** (`howland_refbias.cir`): return R10 and
R11 to a buffered, decoupled VDD/2 instead of Earth. No coupling cap.

| Quantity | Value |
|---|---|
| Load current | 2.0035 mA p-p (unchanged) |
| `V(A_OUT)` | 1.650 V ± 1.399 V (0.251 … 3.049 V) |
| `V(B_OUT)` | 1.650 V ± 1.647 V (0.003 … 3.297 V) |

Outputs are centred on 1.65 V, so the positive swing runs closer to the
rail than with option A.

## Parts-constrained build

The inventory is 10×47k, 10×10k, 10×10 µF, 10×0.1 µF, one 50k trimpot and one
spare TL082. The ideal R8 = R13 = 1 kΩ is not available; the practical builds
below use 3×10k in parallel (3.33k) or 2×10k in parallel (5k) for each
current-setting resistor. The spare TL082 buffers a 2.5 V reference for the
AD620, which allows a DC-coupled receive path.

`../bleed_parts_build.kicad_sch` is a standalone KiCad sheet of this build (A2,
fully wired, **0.6 mA build**). It is derived from `bleed.kicad_sch` without
modifying it, and fixes the topology issues listed further down: Kelvin sense
into the AD620, AD620 V− on −5 V, REF on the buffered 2.5 V, the input HPF, and
R8/R13 = 2×10k (5k). The 50k trimpot is the AD620 RG trimmer; the input HPF DC
return is a fixed 10k (R17), and the sense DC return is a fixed 10k (R19) from
`Drive+` to Earth.

Local connections are drawn as wires, not made through net labels. The AD5933
decoupling bank (C21, C5, C11, C4, C6) sits across the +5 V and Earth rails
that run straight into pins 9–11 and 12–14, and the I²C pull-ups (R1/R2) and
RFB (R3) are wired to their own pins. The whole `CurrentOut` node — C17, the
HPF DC return R17 and both Howland halves — is one continuous wire. Only five
net names still exist as global labels: `VOUT`, `Drive+`, `Drive-` and
`AD620_OUT` for the four signals that run between functional blocks, plus
`AmpOut`, which is a fully wired node (R3, R4, U1 pin 5) labelled only to keep
the reference design's terminology. `RL1` appears only in a note as the
external load; it is not placed on this sheet. ERC reports no errors; the
three remaining warnings are the AD5933 symbol's unconfigured library nickname,
its `RS_16_ADI` footprint, and the RFB pin's pin type.

### 2.5 V reference from the spare TL082

Use one half of the spare TL082 as a unity-gain buffer:

```
+5V ──47k──┬── TL082 +in
            │
          0.1µF
            │
GND ──47k──┴── (divider midpoint)
```

Connect the TL082 output back to its −in and to AD620 pin 5 (REF). The
divider is unloaded by the JFET input, so the output is 2.500 V; with the
AD620's ≈20 kΩ REF input (≈125 µA) the simulated output is still 2.500 V.
Power the spare TL082 from **+5 V and −5 V** (not a single 5 V rail; the
TL082 needs at least 7 V total supply). Tie the unused half off: +in to
ground, −in to its output. Add 0.1 µF from each supply to ground.

### Receive path

* Move AD620 pin 4 (V−) from Earth to **−5 V**. Pin 7 stays at +5 V.
* AD620 pin 5 (REF) to the buffered 2.5 V.
* AD620 pin 6 (OUT) → R4 = 10k → AD5933 pin 5 (VIN). **No coupling capacitor
  is needed**: the AD620 output and the AD5933 VIN are both at 2.5 V DC, so
  there is no DC current through R4.
* AD620 RG: leave pins 1/8 open for G = 1 (0.9 mA build), or fit the 50k
  trimpot for G = 2…100 (0.6 mA build).

The input high-pass is still required. Without it the AD5933 VOUT bias
propagates to the TL082 outputs and the 2000 mV p-p range at 5 V clips U5B.
Fit 10 µF from U1 pin 6 (VOUT) to `CurrentOut` (+ terminal to VOUT) and a DC
return from `CurrentOut` to ground.

### Current-setting resistors

| Build | R8 = R13 | AD5933 range at 5 V | Simulated load current | Input DC return | AD620 gain |
|---|---|---|---|---|---|
| **0.9 mA** | 3×10k ∥ = 3.33k | 2000 mV p-p (3.00 V p-p) | **0.913 mA p-p** | 50k trimpot set ≈47k | 1 (RG open) |
| **0.6 mA** | 2×10k ∥ = 5k | 2000 mV p-p (3.00 V p-p) | **0.626 mA p-p** | 10k (R17) | 2…100 (50k trimpot) |

Both are within the parts count. The 0.9 mA build uses the trimpot as the
input DC return and leaves RG open; the 0.6 mA build uses the trimpot as RG
and a fixed 10k as the input DC return. The 0.6 mA build also needs R19 (the
sense DC return); it shunts the drive node with 10k and costs about 2 % of
current (0.614 → 0.626 mA p-p, so it is slightly over 0.6 mA rather than
under).

### Parts allocation

**0.9 mA build (exactly 10×47k and 10×10k):**

| Value | Use | Count |
|---|---|---|
| 47k | bridge R6, R7, R9, R10, R11, R12, R14, R15 | 8 |
| 47k | 2.5 V divider (47k + 47k) | 2 |
| 10k | R1, R2 I²C pull-ups | 2 |
| 10k | R3 (RFB), R4 (VIN input) | 2 |
| 10k | R8, R13 (3 in parallel each) | 6 |
| 50k trimpot | input HPF DC return, set ≈47k | 1 |
| 10 µF | input DC-blocking capacitor | 1 |
| 0.1 µF | 2.5 V divider bypass | 1 |
| 0.1 µF | C2, C3 output coupling | 2 |
| spare TL082 | 2.5 V buffer (one half) | 1 |

**0.6 mA build (exactly 10×47k and 10×10k, no spare):**

| Value | Use | Count |
|---|---|---|
| 47k | bridge | 8 |
| 47k | 2.5 V divider | 2 |
| 10k | R1, R2 | 2 |
| 10k | R3, R4 | 2 |
| 10k | R8, R13 (2 in parallel each) | 4 |
| 10k | input HPF DC return (R17) | 1 |
| 10k | sense DC return (R19) | 1 |
| 50k trimpot | AD620 RG | 1 |
| 10 µF | input DC-blocking capacitor | 1 |
| 0.1 µF | 2.5 V divider bypass | 1 |
| 0.1 µF | C2, C3 | 2 |

### Simulated results (0.9 mA build)

| Quantity | Value |
|---|---|
| Load current, RL = 1k | **0.913 mA p-p** |
| Load current, RL = 100 Ω … 10 kΩ | 0.918 … 0.849 mA p-p |
| V(A_OUT) | ±1.17 V |
| V(B_OUT) | ±2.36 V |
| Input node DC | 0 V (VOUT bias removed) |
| Buffered 2.5 V into 20 kΩ | 2.500 V |

### Full-chain simulation (bench phantom)

`afe_parts_build.cir` and `afe_parts_loads.cir` simulate the pump and receive
chain with a resistor between `Drive+` and `Drive−` and the AD620 inputs taken
straight from those two nodes — the bench-phantom configuration, which is how
you would test the board with a resistor instead of a body. They are **not**
the sheet's routing: `../bleed_parts_build.kicad_sch` is tetrapolar, with
`Sense±` coming from a separate electrode pair (see the abdominal section).
Neither deck includes R19; with it the pump current is about 2 % higher.

The rest is as drawn: C17 + R17 input HPF, both Howland halves with 47k
bridges and 2×10k (5k) current resistors, the AD620 with RV1 = 50k across RG,
the buffered 2.5 V REF, and R4 into the AD5933 VIN (modelled as the receive
stage's virtual ground at VDD/2). The AD620 has no LTspice model installed, so
it is built from its real internal topology — three op-amps with the
datasheet's 24.7k gain resistors — which reproduces G = 1 + 49.4k/RG from the
actual RV1.

| AD5933 range at 5 V | VOUT | Load current (p-p) | RMS | Peak | V(Drive+) − V(Drive−) | AD620 out |
|---|---|---|---|---|---|---|
| 1000 mV p-p | 1.47 V p-p | **0.301 mA** | 0.106 mA | 0.150 mA | 0.301 V p-p | 2.201 … 2.799 V |
| 2000 mV p-p | 3.00 V p-p | **0.614 mA** | 0.217 mA | 0.307 mA | 0.614 V p-p | 1.890 … 3.110 V |

Both are at RL = 1 kΩ. The input HPF passes 50 kHz unattenuated and the
`CurrentOut` DC is < 0.1 mV, so the VOUT bias is fully removed. Measured gain
`V(AMP_OUT)` / `V(Drive+,Drive−)` = **1.989**, matching 1 + 49.4k/50k. The
load-current distortion (Fourier, 9 harmonics) is **0.0004 %** — no pump
oscillation or clipping at these levels.

Load sweep at the 2000 mV p-p range (`afe_parts_loads.cir`):

| RL | Load current p-p | Load current RMS | AD620 out |
|---|---|---|---|
| 100 Ω | 0.616 mA | 0.218 mA | 2.44 … 2.56 V |
| 470 Ω | 0.615 mA | 0.218 mA | 2.21 … 2.79 V |
| 1 kΩ | 0.614 mA | 0.217 mA | 1.89 … 3.11 V |
| 2.2 kΩ | 0.610 mA | 0.216 mA | 1.17 … 3.77 V |
| 3.3 kΩ | 0.606 mA | 0.214 mA | 0.51 … 4.03 V — starting to clip |
| 4.7 kΩ | 0.602 mA | 0.213 mA | −0.31 … 4.31 V — clipped |
| 10 kΩ | 0.583 mA | 0.207 mA | −3.33 … 4.57 V — clipped |

The pump holds **0.583 … 0.616 mA p-p** over a 100:1 load range — worst case
0.308 mA peak, comfortably under the 1 mA target. In this bench configuration
the receive path runs out first: with G ≈ 2 the AD620 leaves its output range
above RL ≈ 2.5 kΩ. That limit is a property of sensing the full load voltage;
in the tetrapolar circuit the AD620 never sees the load voltage (next section).

### Abdominal (tetrapolar) operation

The sheet drives one electrode pair and senses a different, non-overlapping
pair (`Sense±` → U4.3/U4.2), as `docs/eit-bioimpedance/` requires. Two things
follow.

**The AD620 sees only the tissue transfer impedance.** Contact impedance sits
in the drive loop, where the current source absorbs it; it barely appears at
the sense pair. The model used in `afe_body.cir` / `afe_body_loads.cir` is:

```
Drive+ --Rc-- A --Rt-- B --Rc-- Drive-
               |           |
              Rc          Rc        Rc = one gel contact (0.1 - 4.7 kΩ)
               |           |
            Sense+      Sense-     Rt = transfer impedance (10 - 50 Ω)
```

**The network is floating at DC.** C2/C3 block DC, so with no bias path the
AD620's 1 nA input bias current walks its inputs to a rail within seconds.
R19 (10k from `Drive+` to Earth) fixes that. It must sit on a drive node, not
on an AD620 input: a single resistor from `Sense+` to Earth unbalances the
sense pair and adds 300 Ω / 10 kΩ ≈ 3 % of the drive voltage directly to the
differential signal — the simulated apparent gain jumps from 1.97 to 4.46
(`afe_body.cir` steps both nodes; the `RBIAS` comment explains). A matched pair
of resistors on both inputs would also work, but only one 10k is left.

At the 2000 mV p-p range the pump delivers **0.626 mA p-p** (0.221 mA RMS,
0.313 mA peak) through the body, and the current is independent of the tissue
and contact impedances:

| Transfer Z | Sense voltage p-p | AD620 out, G = 2 (RG = 50k) | G = 10.9 (RG = 4.95k) |
|---|---|---|---|
| 10 Ω | 6.26 mV | 12.5 mV p-p | 68.5 mV p-p |
| 20 Ω | 12.5 mV | 24.9 mV | 137.0 mV |
| 50 Ω | 31.3 mV | 62.2 mV | 342.4 mV |

The AD620 output stays between 2.33 and 2.67 V — no headroom problem. At the
1000 mV p-p range every voltage in this table halves.

Contact sweep (`afe_body_loads.cir`, Rt = 20 Ω, G = 10.9):

| Contact R (each) | Drive voltage p-p | Sense p-p | AD620 out | Current p-p |
|---|---|---|---|---|
| 100 Ω | 0.138 V | 12.57 mV | 137.5 mV | 0.629 mA |
| 300 Ω | 0.388 V | 12.52 mV | 137.0 mV | 0.626 mA |
| 1 kΩ | 1.248 V | 12.36 mV | 135.2 mV | 0.618 mA |
| 2.2 kΩ | 2.670 V | 12.08 mV | 132.2 mV | 0.604 mA |
| 4.7 kΩ | 5.054 V | 10.73 mV | 117.5 mV | 0.537 mA |

The sense voltage is flat to 4 % up to 2.2 kΩ per electrode; only at 4.7 kΩ
does the drive voltage reach the ±5 V compliance limit and the current sag
(and with it the sensed signal, by 15 %). Use the 1000 mV p-p range if contact
quality is unknown — it halves the required drive voltage. The CD74HC4067
muxes add roughly 100 Ω of on-resistance in series with each electrode; in the
drive loop that is just more contact resistance, and in the sense loop it
carries only the AD620's nanoamps.

Frequency response (`afe_body_ac.cir`, Rt = 20 Ω, G = 10.9), transconductance
relative to 50 kHz:

| Frequency | Value | Relative |
|---|---|---|
| 500 Hz | 0.176 mA/V | −16 % |
| 1 kHz | 0.198 mA/V | −4.7 % |
| 2 kHz | 0.206 mA/V | −1.3 % |
| 5 kHz | 0.208 mA/V | −0.3 % |
| 10 kHz | 0.208 mA/V | −0.1 % |
| 50 kHz | 0.208 mA/V | reference |
| 100 kHz | 0.209 mA/V | +0.2 % |
| 200 kHz | 0.213 mA/V | +2 % |
| 500 kHz | 0.236 mA/V | +13 % |
| 1 MHz | 0.378 mA/V | +81 % |

Flat within 1 % from about 3 kHz to 300 kHz, which covers the AD5933's whole
1 kHz–100 kHz range. Stay below ~300 kHz: the pump peaks sharply towards
1 MHz.

**Gain.** `docs/eit-bioimpedance/README.md` expects an instrumentation-amp gain
of 10–50; the AD620 needs RG = 49.4k/(G−1), i.e. **4.95k for G = 10.9** (the
trimpot at about a tenth of its travel, which the simulation uses) and
**1.27k for G = 40**. G ≈ 11 puts a 10–100 Ω transfer impedance at 68–684 mV
p-p, the right range for the AD5933's 12-bit converter and its ×1/×5 receive
PGA. G = 40 helps only for small transfer impedances: at 50 Ω it gives 1.25 V
p-p, and at 100 Ω 2.5 V p-p, which is just inside the AD620's 2.5 V + 1.4 V
positive headroom. A trimpot is fine for development but its 100–250 ppm/°C
drift is comparable to the 0.1–1 % changes EIT is looking for; for a final
build replace RV1 with a fixed resistor and calibrate against a known one.
Keep the sense electrodes Ag/AgCl: at G = 40 a few mV of half-cell mismatch is
fine, but hundreds of mV (other electrode types) would use up the headroom, and
the receive chain is DC-coupled.

**Safety.** At 50 kHz the design runs at 0.221 mA RMS. IEC 60601-1 patient
auxiliary current (between electrodes, normal condition) is 100 µA from
0.1 Hz–1 kHz, then 100·f µA (f in kHz) up to 100 kHz, so the limit at 50 kHz
is 5 mA — the pump uses **4.4 % of it**. The limit falls steeply below that:

| Frequency | Design current | IEC limit | Ratio |
|---|---|---|---|
| 50 kHz | 0.221 mA RMS | 5 mA | 4 % |
| 10 kHz | 0.221 mA | 1 mA | 22 % |
| 2 kHz | 0.218 mA | 0.2 mA | 109 % |
| 1 kHz | 0.211 mA | 0.1 mA | 211 % |

So the 2000 mV p-p range is compliant above about **2.2 kHz**. For a sweep
that goes lower, drop to the 400 mV p-p range (0.044 mA RMS, 44 % of the
1 kHz limit) or the 200 mV range (0.022 mA RMS). There is no DC patient
current: C2/C3 isolate the load, and R19 is on the load side of C3.

**Isolation is not in this design.** C2/C3 are functional coupling caps, not a
safety barrier, and the ground is the Pi's ground. A patient-connected board
must be powered from a battery or a medical-grade isolated supply, with the
leakage current measured. R19 is also a 10 kΩ path from the drive node to
circuit ground — it sets the source impedance for any single-fault current,
so keep the supply isolated rather than relying on it.

### AC response (R8 = R13 = 1k, 1 kΩ load)

| Frequency | Transconductance |
|---|---|
| 1 kHz | 0.532 mA/V |
| 5 kHz | 0.953 mA/V |
| 10 kHz | 0.988 mA/V |
| 50 kHz | 1.002 mA/V |
| 100 kHz | 1.008 mA/V |
| 300 kHz | 1.075 mA/V |
| 955 kHz | **1.81 mA/V** (peak, ~+5 dB) |
| 1.5 MHz | −3 dB vs 50 kHz |

The 0.1 µF coupling caps set a high-pass corner near **1.5 kHz**. There is
significant peaking near 1 MHz — verify with a real TL082 before running the
pump near/beyond that.

## Recommendation

**With the parts on hand**, use the **0.6 mA build** — the one drawn in
`../bleed_parts_build.kicad_sch`: R8 = R13 = 5k (2×10k in parallel), AD5933 at
5 V with the 2000 mV p-p range, input HPF with a fixed 10k DC return, buffered
2.5 V at the AD620 REF, R19 = 10k as the sense DC return, and the 50k trimpot
as RG (G ≈ 2 at 50k, rising as it is wound down). It uses the whole 10×47k /
10×10k inventory with nothing spare and gives 0.626 mA p-p. The 0.9 mA build
(R8/R13 = 3.33k, trimpot as the input DC return, RG open) gives 0.913 mA p-p
but has no gain control and no sense DC return, so it is not usable as drawn
against a tetrapolar body.

For the abdomen, set RV1 to about 4.95k (G = 10.9) rather than 50k: 0.626 mA
p-p into a 10–100 Ω transfer impedance then gives 68–684 mV p-p at the AD620,
which is a sensible level for the AD5933. At 50 kHz that is 0.221 mA RMS, 4 %
of the 5 mA IEC 60601-1 patient auxiliary current limit; below about 2.2 kHz
drop to a lower AD5933 excitation range to stay inside the 100 µA–1 mA part
of the limit.

The ideal reference operating point still needs R8 = R13 = 1 kΩ, which is not
available from 10k/47k parts (ten 10k per side would be needed for the two
resistors). If 1 kΩ parts are added later:

* 1 V p-p excitation → ~1 mA p-p (0.5 mA peak)
* 2 V p-p excitation → ~1 mA peak (2 mA p-p)

At 5 V the 1000 mV p-p range becomes 1.47 V p-p, so Rs ≈ 1.5k keeps ~1 mA p-p.

In every case, add the input high-pass (series cap + DC return, e.g.
10 µF + 10k here, corner ≈1.6 Hz, or the reference's 10 nF + 100k for ≥1 kHz
only). It
centres the pump outputs on 0 V, removes the AD5933 bias from the op-amp
headroom, and makes the current independent of the excitation range and
supply. The existing 0.1 µF output caps (C2/C3) do **not** do this — they only
keep DC out of the load.

## Files

| File | Purpose |
|---|---|
| `ADTL082.lib` | ADI TL082 macromodel (from LTspice `lib/sub/ADI.lib`) |
| `AD620.lib` | Behavioural AD620 model: three op-amps with the datasheet 24.7k gain resistors |
| `howland_asdrawn.cir` | All 47k, 1 V p-p — baseline |
| `howland_sweep.cir` | Steps R8/R13 through 47k … 1k |
| `howland_loadsweep.cir` | R8/R13 = 1k, steps RL 100 Ω … 10 kΩ |
| `howland_dcbias.cir` | Steps VOUT DC bias 0 / 1.65 / 2.5 V |
| `howland_1mA_peak.cir` | 2 V p-p, 1k — the 1 mA-peak operating point |
| `howland_ac.cir` | AC transconductance, 1 kHz – 10 MHz |
| `howland_refbias.cir` | R10/R11 returned to a 1.65 V reference |
| `howland_accouple.cir` | Input AC-coupled with a 470k DC return |
| `howland_5v_r1.cir` | 5 V AD5933, 2000 mV p-p range (clips) |
| `howland_5v_r2.cir` | 5 V AD5933, 1000 mV p-p range |
| `howland_5v_r1_cap.cir` | 5 V, 2000 mV p-p range, input HPF fitted |
| `howland_parts_50k.cir` | Parts-constrained 0.9 mA build: R8/R13 = 3.33k, 50k DC return |
| `howland_parts_5k.cir` | Parts-constrained 0.6 mA build: R8/R13 = 5k, 10k DC return |
| `howland_parts_loads.cir` | Load sweep (100 Ω … 10 kΩ) for the 3.33k build |
| `afe_parts_build.cir` | Full chain, bench phantom (HPF, both Howlands, AD620 with RV1, 2.5 V ref, AD5933 VIN), both excitation ranges |
| `afe_parts_loads.cir` | Same bench phantom, RL swept 100 Ω … 10 kΩ |
| `afe_body.cir` | Tetrapolar abdominal case: transfer impedance 10/20/50 Ω × RG 50k/4.95k, with and without the sense DC return |
| `afe_body_loads.cir` | Tetrapolar abdominal case, contact resistance swept 100 Ω … 4.7 kΩ |
| `afe_body_ac.cir` | Tetrapolar abdominal case, transconductance 500 Hz … 2 MHz |
| `ref25_buffer.cir` | Spare-TL082 buffered 2.5 V reference (47k/47k divider) |
| `make_schematics.py` | Regenerates the `.asc` schematic next to each `.cir` bench |

Run one headlessly:

```sh
wine "/home/conleth/.wine/drive_c/Program Files/ADI/LTspice/LTspice.exe" \
  -b "Z:\\home\\conleth\\Documents\\code\\crimson-veil\\bleed\\sim\\howland_asdrawn.cir"
```

Measurements land in the `.log` next to the netlist; open the same `.cir` in
the LTspice GUI for waveforms.

Every `.cir` bench also has a matching `.asc` schematic with the same topology
and values. Open the `.asc` in the LTspice GUI to inspect the circuit or take a
screenshot. After changing a bench, run `python3 make_schematics.py` to rebuild
the whole `.asc` set.

## Caveats

* The `ADTL082` macromodel is characterised for ±15 V. At ±5 V its output
  swing/rail behaviour is only approximate; confirm the bias margins on the
  bench.
* The AD5933 is specified for 2.7–5.5 V, so the KiCad net's +5 V on pins
  9/10/11 is within spec. Remember that the output amplitude and bias scale
  with VDD, and that the bias is range-dependent (see the table above).
  The reference design uses the 1000 mV p-p range; at 5 V that becomes
  1.47 V p-p, so Rs = 1k gives ~1.5 mA p-p. Rs ≈ 1.5k restores ~1 mA p-p.
  If the AD5933 is a module with its own 3.3 V regulator, measure VOUT: a
  ~0.76 V bias means the die is at 3.3 V, ~1.15 V means 5 V.
* `I(R8)`/`I(R13)` is the sense current; the load current differs by the
  feedback-divider current at large Rs.
