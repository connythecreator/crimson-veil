#!/usr/bin/env python3
"""Generate the LTspice .asc schematics for the benches in this directory.

Every .cir bench has a matching .asc schematic with the same topology and
values.  The .cir files remain the numeric source of truth; the .asc files
are for opening in the LTspice GUI and for screenshots.

Usage:  python3 make_schematics.py

ASCII only: values use 'u' for micro, so the files are valid Windows-1252.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent


def res_h(name, value, x1, y):
    """Horizontal resistor, left pin (x1,y), right pin (x1+80,y)."""
    return [f"SYMBOL res {x1 + 96} {y - 16} R90",
            f"SYMATTR InstName {name}",
            f"SYMATTR Value {value}"]


def res_v(name, value, x, y1):
    """Vertical resistor, top pin (x,y1), bottom pin (x,y1+80)."""
    return [f"SYMBOL res {x - 16} {y1 - 16} R0",
            f"SYMATTR InstName {name}",
            f"SYMATTR Value {value}"]


def cap_h(name, value, x1, y):
    """Horizontal capacitor, left pin (x1,y), right pin (x1+64,y)."""
    return [f"SYMBOL cap {x1 + 64} {y - 16} R90",
            f"SYMATTR InstName {name}",
            f"SYMATTR Value {value}"]


def cap_v(name, value, x, y1):
    """Vertical capacitor, top pin (x,y1), bottom pin (x,y1+64)."""
    return [f"SYMBOL cap {x - 16} {y1} R0",
            f"SYMATTR InstName {name}",
            f"SYMATTR Value {value}"]


def voltage_v(name, value, x, y1):
    """Vertical voltage source, + pin (x,y1), - pin (x,y1+80)."""
    return [f"SYMBOL voltage {x} {y1 - 16} R0",
            f"SYMATTR InstName {name}",
            f"SYMATTR Value {value}"]


def opamp(name, subckt, x, y):
    return [f"SYMBOL opamp2 {x} {y} R0",
            f"SYMATTR InstName {name}",
            f"SYMATTR Value {subckt}"]


def dip8(name, subckt, x, y):
    return [f"SYMBOL DIP8 {x} {y} R0",
            f"SYMATTR InstName {name}",
            f"SYMATTR Value {subckt}"]


def text(x, y, s):
    return f"TEXT {x} {y} Left 2 {s}"


def howland(include_hpf=True, cap="10u", rbias="10k", cap_name="C17",
            bias_name="R17", rs="1k", parallel_rs=False, rl=None,
            input_label="IN", vdc="2.24", vamp="1.5", freq="50k",
            source_name="VOUT", bias_node="0", bias_voltage=None,
            analysis=None, notes=None):
    """Mirrored Howland block. Returns (lines, directives)."""
    L = []
    D = []
    src_val = (f"DC {vdc} AC 1 SINE({vdc} {vamp} {freq})"
               if vamp is not None else f"DC {vdc} AC 1")
    L += voltage_v(source_name, src_val, 80, 240)
    L += ["FLAG 80 320 0"]
    if include_hpf:
        L += [f"FLAG 80 240 {input_label}"]
        L += cap_h(cap_name, cap, 128, 240)
        L += ["WIRE 80 240 128 240", "WIRE 192 240 240 240"]
        L += res_v(bias_name, rbias, 240, 240)
        L += ["FLAG 240 320 0", "WIRE 240 240 240 208",
              "WIRE 240 208 320 208", "FLAG 240 208 IN_NET"]
        in_net = "IN_NET"
    else:
        L += [f"FLAG 80 240 {input_label}"]
        L += ["WIRE 80 240 240 240", "WIRE 240 240 240 208",
              "WIRE 240 208 320 208", f"FLAG 240 208 {input_label}"]
        in_net = input_label

    # --- Howland A ---
    L += res_h("R6", "47k", 320, 208)
    L += res_h("R7", "47k", 528, 160)
    L += res_h("R9", "47k", 608, 288)
    L += res_v("R10", "47k", 528, 256)
    L += opamp("U5A", "ADTL082", 560, 160)
    L += ["FLAG 560 192 VCC", "FLAG 560 256 VEE",
          "WIRE 400 208 528 208",
          "WIRE 528 160 528 208",
          "WIRE 608 160 608 224", "WIRE 608 224 592 224",
          "WIRE 528 240 528 256",
          f"FLAG 528 336 {bias_node}",
          "WIRE 528 240 480 240", "WIRE 480 240 480 288",
          "WIRE 480 288 608 288"]

    if parallel_rs:
        L += res_h("R8", rs, 592, 208)
        L += res_h("R16", rs, 592, 240)
        L += ["WIRE 592 224 592 208", "WIRE 592 224 592 240",
              "WIRE 672 208 672 224", "WIRE 672 240 672 224"]
    else:
        L += res_h("R8", rs, 592, 224)
    L += cap_h("C3", "0.1u", 672, 224)
    L += ["WIRE 736 224 800 224", "WIRE 688 288 800 288"]
    if rl is not None:
        L += res_v("RL", rl, 800, 304)
        L += ["WIRE 800 224 800 304", "WIRE 800 384 800 544",
              "WIRE 800 544 800 640"]
        L += ["FLAG 800 224 DRV_P", "FLAG 800 640 DRV_M"]
    else:
        L += ["WIRE 800 224 800 288", "WIRE 800 544 800 640",
              "FLAG 800 224 DRV_P", "FLAG 800 640 DRV_M"]

    # --- Howland B ---
    L += res_h("R11", "47k", 320, 528)
    L += res_h("R12", "47k", 528, 592)
    L += res_h("R14", "47k", 528, 640)
    L += res_h("R15", "47k", 384, 688)
    L += opamp("U5B", "ADTL082", 560, 480)
    L += ["FLAG 560 512 VCC", "FLAG 560 576 VEE",
          "WIRE 400 528 528 528",
          "WIRE 528 528 480 528", "WIRE 480 528 480 592",
          "WIRE 480 592 528 592",
          "WIRE 608 592 608 544", "WIRE 608 544 592 544",
          "WIRE 528 560 464 560", "WIRE 464 560 464 688",
          "WIRE 464 640 528 640",
          f"FLAG 384 688 {in_net}",
          f"FLAG 320 528 {bias_node}"]

    if parallel_rs:
        L += res_h("R13", rs, 592, 528)
        L += res_h("R18", rs, 592, 560)
        L += ["WIRE 592 544 592 528", "WIRE 592 544 592 560",
              "WIRE 672 528 672 544", "WIRE 672 560 672 544"]
    else:
        L += res_h("R13", rs, 592, 544)
    L += cap_h("C2", "0.1u", 672, 544)
    L += ["WIRE 736 544 800 544", "WIRE 608 640 800 640"]

    # --- rails ---
    L += voltage_v("VCC", "5", 80, 64)
    L += ["FLAG 80 64 VCC", "FLAG 80 144 0"]
    # The symbol's + pin is on top. Ground is the positive end of the negative
    # rail, so the source value is 5 and the bottom pin is VEE = -5 V.
    L += voltage_v("VEE", "5", 80, 704)
    L += ["FLAG 80 704 0", "FLAG 80 784 VEE"]
    if bias_voltage is not None:
        L += voltage_v("VREF", bias_voltage, 80, 520)
        L += ["FLAG 80 520 VREF", "FLAG 80 600 0"]

    y = 900
    if notes:
        for n in notes:
            D.append(text(80, y, ";" + n))
            y += 24
    if analysis:
        for a in analysis:
            D.append(text(80, y, "!" + a))
            y += 24
    return L, D


def make_howland(name, **kw):
    L = ["Version 4.1", "SHEET 1 1000 1200"]
    body, directives = howland(**kw)
    L += body
    L += directives
    (OUT / f"{name}.asc").write_text("\n".join(L) + "\n", encoding="ascii")


def make_afe(name, *, body_model=False, rl="1k", rc="300", rt="20", rg="50k",
             rs="10k", parallel_rs=True, vdc="2.24", vamp="1.5", ac=False,
             steps=None, notes=None, rbias="10k"):
    L = ["Version 4.1", "SHEET 1 1800 1400"]
    body, _ = howland(include_hpf=True, cap="10u", rbias="10k",
                      rs=rs, parallel_rs=parallel_rs, rl=None,
                      input_label="VOUT", vdc=vdc,
                      vamp=vamp if not ac else None,
                      source_name="VOUT")
    L += body

    # --- load or body model ---
    if body_model:
        L += res_h("RCD1", rc, 1000, 200)
        L += res_h("RT", rt, 1080, 200)
        L += res_h("RCD2", rc, 1160, 200)
        L += ["WIRE 1080 200 1080 240", "WIRE 1160 200 1160 240",
              "FLAG 1000 200 DRV_P", "FLAG 1240 200 DRV_M"]
        L += res_v("RCS1", rc, 1080, 240)
        L += res_v("RCS2", rc, 1160, 240)
        L += ["FLAG 1080 320 SP", "FLAG 1160 320 SM"]
        L += res_v("RBIAS", rbias, 1280, 200)
        L += ["FLAG 1280 200 DRV_P", "FLAG 1280 280 0"]
    else:
        L += res_v("RL", rl, 1000, 256)
        L += ["FLAG 1000 256 DRV_P", "FLAG 1000 336 DRV_M"]

    # --- AD620 ---
    inp = "SP" if body_model else "DRV_P"
    inm = "SM" if body_model else "DRV_M"
    L += dip8("U4", "AD620", 1200, 700)
    L += [f"FLAG 1088 604 {inp}", f"FLAG 1088 668 {inm}",
          "FLAG 1312 796 VCC", "FLAG 1312 732 VEE",
          "FLAG 1312 668 VREF", "FLAG 1312 604 AMP_OUT"]
    L += res_h("RV1", rg, 1040, 900)
    L += ["WIRE 1088 732 1040 732", "WIRE 1040 732 1040 900",
          "WIRE 1088 796 1120 796", "WIRE 1120 796 1120 900"]

    # --- 2.5 V reference ---
    L += res_v("R20", "47k", 1040, 1000)
    L += ["FLAG 1040 1000 VCC"]
    L += res_v("R21", "47k", 1040, 1080)
    L += ["FLAG 1040 1160 0"]
    L += cap_v("C18", "0.1u", 1080, 1080)
    L += ["WIRE 1040 1080 1080 1080", "FLAG 1080 1144 0"]
    L += opamp("U6A", "ADTL082", 1200, 1040)
    L += ["FLAG 1200 1072 VCC", "FLAG 1200 1136 VEE",
          "WIRE 1040 1080 1120 1080", "WIRE 1120 1080 1120 1120",
          "WIRE 1120 1120 1168 1120",
          "WIRE 1232 1104 1280 1104", "WIRE 1280 1104 1280 1088",
          "WIRE 1280 1088 1168 1088", "FLAG 1280 1104 VREF"]

    # --- AD5933 VIN model ---
    L += res_h("R4", "10k", 1440, 700)
    L += ["FLAG 1440 700 AMP_OUT"]
    L += voltage_v("VVIN", "2.5", 1520, 700)
    L += ["FLAG 1520 780 0"]

    # --- directives ---
    d = ["!.include ADTL082.lib", "!.include AD620.lib"]
    d.append("!.ac dec 20 500 2meg" if ac else "!.tran 0 2m 0 0.05u")
    if steps:
        d.extend("!" + s for s in steps)
    if notes:
        d = [";" + n for n in notes] + d
    y = 1000
    for s in d:
        L.append(text(80, y, s))
        y += 24

    (OUT / f"{name}.asc").write_text("\n".join(L) + "\n", encoding="ascii")


def make_ref25():
    L = ["Version 4.1", "SHEET 1 900 700"]
    L += voltage_v("VCC", "5", 80, 64)
    L += ["FLAG 80 64 VCC", "FLAG 80 144 0"]
    # + pin on top at ground, bottom pin at VEE: value 5 makes VEE = -5 V.
    L += voltage_v("VEE", "5", 80, 400)
    L += ["FLAG 80 400 0", "FLAG 80 480 VEE"]
    L += res_v("R1", "47k", 240, 160)
    L += ["FLAG 240 160 VCC"]
    L += res_v("R2", "47k", 240, 240)
    L += ["FLAG 240 320 0", "FLAG 240 240 VREF"]
    L += cap_v("C1", "0.1u", 280, 240)
    L += ["WIRE 240 240 280 240", "FLAG 280 304 0"]
    L += opamp("U6", "ADTL082", 400, 240)
    L += ["FLAG 400 272 VCC", "FLAG 400 336 VEE",
          "WIRE 240 240 320 240", "WIRE 320 240 320 320",
          "WIRE 320 320 368 320",
          "WIRE 432 304 480 304", "WIRE 480 304 480 288",
          "WIRE 480 288 368 288", "FLAG 480 304 VOUT"]
    L += res_v("RREF", "20k", 520, 304)
    L += ["FLAG 520 304 VOUT", "FLAG 520 384 0"]
    L += [text(80, 560, "!.include ADTL082.lib"),
          text(80, 584, "!.tran 0 20m 0 10u"),
          text(80, 608, "!.meas tran vout_avg AVG V(VOUT) FROM 15m TO 20m"),
          text(80, 632, "!.meas tran vref_avg AVG V(VREF) FROM 15m TO 20m"),
          text(80, 656, "!.meas tran i_load AVG I(RREF) FROM 15m TO 20m")]
    (OUT / "ref25_buffer.asc").write_text("\n".join(L) + "\n", encoding="ascii")


# ---------------------------------------------------------------- generators
make_howland("howland_1mA_peak", include_hpf=False, rs="1k", rl="1k",
             input_label="IN", vdc="1.65", vamp="1.0",
             notes=["Mirrored Howland, 1 mA peak operating point",
                    "2 V p-p input, R8=R13=1k, 47k bridge, RL=1k"],
             analysis=[".include ADTL082.lib", ".tran 0 20m 0 0.05u",
                       ".meas tran vin_pp PP V(IN) FROM 19m TO 20m",
                       ".meas tran iL_pp PP I(RL) FROM 19m TO 20m",
                       ".meas tran vL_pp PP V(DRV_P,DRV_M) FROM 19m TO 20m"])

make_howland("howland_asdrawn", include_hpf=False, rs="47k", rl="1k",
             input_label="IN", vdc="0", vamp="0.5",
             notes=["As drawn: every resistor 47k",
                    "R8/R13=47k gives only 26.5 uA p-p, not 1 mA"],
             analysis=[".include ADTL082.lib", ".tran 0 400u 0 0.02u",
                       ".meas tran iL_pp PP I(RL) FROM 300u TO 400u",
                       ".meas tran ir8_pp PP I(R8) FROM 300u TO 400u",
                       ".meas tran ir13_pp PP I(R13) FROM 300u TO 400u"])

make_howland("howland_loadsweep", include_hpf=False, rs="1k", rl="{RL}",
             input_label="IN", vdc="0", vamp="0.5",
             notes=["Load sweep: 100 ohm to 10k",
                    "Current should stay flat (current-source behaviour)"],
             analysis=[".include ADTL082.lib", ".param RL 1k",
                       ".step param RL list 100 470 1k 2.2k 4.7k 10k",
                       ".tran 0 400u 0 0.02u"])

make_howland("howland_ac", include_hpf=False, rs="1k", rl="1k",
             input_label="IN", vdc="0", vamp=None,
             notes=["AC response of the Howland stage"],
             analysis=[".include ADTL082.lib", ".ac dec 50 1k 10Meg"])

make_howland("howland_dcbias", include_hpf=False, rs="1k", rl="1k",
             input_label="IN", vdc="{VDC}", vamp="0.5",
             notes=["VOUT DC bias sweep: 0, 1.65, 2.5 V"],
             analysis=[".include ADTL082.lib", ".param VDC 1.65",
                       ".step param VDC list 0 1.65 2.5",
                       ".tran 0 20m 0 0.05u"])

make_howland("howland_accouple", include_hpf=True, cap="1u", rbias="470k",
             cap_name="CIN", bias_name="RBIAS", rs="1k", rl="1k",
             input_label="IN", vdc="0", vamp="1.0",
             notes=["AC-coupled input: CIN=1u, RBIAS=470k",
                    "Removes the AD5933 VOUT DC bias from the pump"],
             analysis=[".include ADTL082.lib", ".tran 0 20m 0 0.05u",
                       ".meas tran iL_pp PP I(RL) FROM 19m TO 20m"])

make_howland("howland_parts_5k", include_hpf=True, cap="10u", rbias="10k",
             cap_name="CIN", bias_name="RBIAS", rs="5k", rl="1k",
             input_label="IN", vdc="0", vamp="1.5",
             notes=["Parts build: R8=R13=5k (2x10k), RBIAS=10k",
                    "0.6 mA p-p from 3 V p-p"],
             analysis=[".include ADTL082.lib", ".tran 0 20m 0 0.05u",
                       ".meas tran iL_pp PP I(RL) FROM 19m TO 20m"])

make_howland("howland_5v_r1", include_hpf=False, rs="1k", rl="1k",
             input_label="IN", vdc="2.24", vamp="1.5",
             notes=["AD5933 at 5 V, 2000 mV p-p range",
                    "VOUT = 3.00 V p-p biased at 2.24 V"],
             analysis=[".include ADTL082.lib", ".tran 0 20m 0 0.05u",
                       ".meas tran iL_pp PP I(RL) FROM 19m TO 20m"])

make_howland("howland_5v_r1_cap", include_hpf=True, cap="1u", rbias="470k",
             cap_name="CIN", bias_name="RBIAS", rs="1k", rl="1k",
             input_label="IN", vdc="0", vamp="1.5",
             notes=["5 V build with the input HPF fitted",
                    "CIN=1u, RBIAS=470k; removes the 2.24 V bias"],
             analysis=[".include ADTL082.lib", ".tran 0 20m 0 0.05u",
                       ".meas tran iL_pp PP I(RL) FROM 19m TO 20m"])

make_howland("howland_5v_r2", include_hpf=False, rs="1k", rl="1k",
             input_label="IN", vdc="1.152", vamp="0.735",
             notes=["AD5933 at 5 V, 1000 mV p-p range",
                    "VOUT = 1.47 V p-p biased at 1.152 V"],
             analysis=[".include ADTL082.lib", ".tran 0 20m 0 0.05u",
                       ".meas tran iL_pp PP I(RL) FROM 19m TO 20m"])

make_howland("howland_5v_r2_dc", include_hpf=False, rs="1k", rl="1k",
             input_label="IN", vdc="1.152", vamp="0.735",
             notes=["1000 mV p-p range: DC and AC load current"],
             analysis=[".include ADTL082.lib", ".tran 0 20m 0 0.05u",
                       ".meas tran iL_pp PP I(RL) FROM 19m TO 20m",
                       ".meas tran iL_dc AVG I(RL) FROM 19m TO 20m",
                       ".meas tran vp_dc AVG V(DRV_P) FROM 19m TO 20m",
                       ".meas tran vm_dc AVG V(DRV_M) FROM 19m TO 20m"])

make_howland("howland_parts", include_hpf=True, cap="10u", rbias="47k",
             cap_name="CIN", bias_name="RBIAS", rs="3.33k", rl="1k",
             input_label="IN", vdc="0", vamp="1.5",
             notes=["Parts build: R8=R13=3.33k (3x10k), RBIAS=47k",
                    "Input HPF CIN=10u"],
             analysis=[".include ADTL082.lib", ".tran 0 20m 0 0.05u",
                       ".meas tran iL_pp PP I(RL) FROM 19m TO 20m"])

make_howland("howland_parts_50k", include_hpf=True, cap="10u", rbias="50k",
             cap_name="CIN", bias_name="RBIAS", rs="3.33k", rl="1k",
             input_label="IN", vdc="0", vamp="1.5",
             notes=["Parts build: R8=R13=3.33k (3x10k), RBIAS=50k",
                    "50k is the value of the spare trimpot"],
             analysis=[".include ADTL082.lib", ".tran 0 20m 0 0.05u",
                       ".meas tran iL_pp PP I(RL) FROM 19m TO 20m"])

make_howland("howland_parts_loads", include_hpf=True, cap="10u", rbias="50k",
             cap_name="CIN", bias_name="RBIAS", rs="3.33k", rl="{RL}",
             input_label="IN", vdc="0", vamp="1.5",
             notes=["Parts build load sweep: 100 ohm to 10k",
                    "R8=R13=3.33k, RBIAS=50k"],
             analysis=[".include ADTL082.lib", ".param RL 1k",
                       ".step param RL list 100 470 1k 2.2k 4.7k 10k",
                       ".tran 0 20m 0 0.05u",
                       ".meas tran iL_pp PP I(RL) FROM 19m TO 20m"])

make_howland("howland_refbias", include_hpf=False, rs="1k", rl="1k",
             input_label="IN", vdc="1.65", vamp="1.0",
             bias_node="VREF", bias_voltage="1.65",
             notes=["Feedback dividers returned to a 1.65 V reference",
                    "No input coupling cap; outputs centre on 1.65 V"],
             analysis=[".include ADTL082.lib", ".tran 0 20m 0 0.05u",
                       ".meas tran iL_pp PP I(RL) FROM 19m TO 20m"])

make_howland("howland_sweep", include_hpf=False, rs="{RS}", rl="1k",
             input_label="IN", vdc="0", vamp="0.5",
             notes=["Current-setting resistor sweep",
                    "R8=R13 stepped 47k down to 1k"],
             analysis=[".include ADTL082.lib", ".param RS 47k",
                       ".step param RS list 47k 22k 10k 4.7k 2.2k 1k",
                       ".tran 0 400u 0 0.02u",
                       ".meas tran iL_pp PP I(RL) FROM 300u TO 400u"])

# ------------------------------------------------------------------- AFEs
make_afe("afe_parts_build", body_model=False, rl="1k", rg="50k",
         vamp="{VAMP}",
         steps=[".param VAMP 1.5", ".step param VAMP list 1.5 0.735"],
         notes=["Parts-constrained AFE: 5k current-set, AD620, 2.5 V ref",
                "AD5933 output 3.00 V p-p at 2.24 V bias",
                "RL = 1k electrode/load stand-in"])

make_afe("afe_parts_loads", body_model=False, rl="{RL}", rg="50k",
         steps=[".param RL 1k",
                ".step param RL list 100 470 1k 2.2k 3.3k 4.7k 10k"],
         notes=["AFE load sweep: 100 ohm to 10k"])

make_afe("afe_body", body_model=True, rc="300", rt="{RTIS}", rg="{RG}",
         rbias="{RBIAS}",
         steps=[".param RTIS 20", ".param RG 50k", ".param RBIAS 1e12",
                ".step param RTIS list 10 20 50",
                ".step param RG list 50k 4.95k",
                ".step param RBIAS list 1e12 10k"],
         notes=["Tetrapolar body model: drive contact, tissue, sense contact",
                "RTIS swept 10/20/50 ohm; RG 50k/4.95k",
                "RBIAS swept 1e12 (none) and 10k (spare part)"])

make_afe("afe_body_loads", body_model=True, rc="{RC}", rt="20", rg="4.95k",
         steps=[".param RC 300",
                ".step param RC list 100 300 1k 2.2k 4.7k"],
         notes=["Electrode contact sweep: 100 ohm to 4.7k",
                "Sensed voltage should stay nearly flat (tetrapolar)"])

make_afe("afe_body_ac", body_model=True, rc="300", rt="20", rg="4.95k",
         ac=True, notes=["Body model frequency response, 500 Hz to 2 MHz"])

make_ref25()

print("written:")
for p in sorted(OUT.glob("*.asc")):
    print(" ", p.name)
