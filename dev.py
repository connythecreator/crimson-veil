#!/usr/bin/env python3
"""Crimson Veil - development / bring-up tooling.

Separate from the device boot (main.py). Subcommands:

    python dev.py doctor        # report configured backends and dependency status
    python dev.py scan-once     # run one scan via the pipeline -> a PNG file
    python dev.py calibrate     # gain/phase calibration (stub until hardware exists)

On real hardware the bring-up order is: doctor -> calibrate -> scan-once.
"""

from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def cmd_doctor(_args: argparse.Namespace) -> int:
    from software.core import config

    print("Crimson Veil - doctor")
    print(f"  hardware backend : {config.HARDWARE_BACKEND}")
    print(f"  solver backend   : {config.SOLVER_BACKEND}")
    print(f"  frequency (Hz)   : {config.DEFAULT_FREQUENCY_HZ}")
    print(f"  electrodes       : {config.N_ELECTRODES}")

    print("  dependencies     :")
    for mod in ("serial",):
        try:
            __import__(mod)
            print(f"    [ok]   {mod}")
        except ImportError:
            print(f"    [----] {mod} (not installed)")

    try:
        hardware = _open_hardware()
        print(f"  backend identity : {hardware.identify()}")
        n = getattr(hardware, "n_electrodes", 0)
        if n:
            print(f"  electrodes (hw)  : {n}")
        hardware.close()
        print("  backend open     : ok")
    except Exception as exc:  # noqa: BLE001
        print(f"  backend open     : FAILED ({type(exc).__name__}: {exc})")
        return 1
    return 0


def cmd_scan_once(args: argparse.Namespace) -> int:
    from software import pipeline

    out = args.output or os.path.join(os.getcwd(), "scan.png")
    data = pipeline.run_scan()
    with open(out, "wb") as handle:
        handle.write(data)
    print(f"wrote {out} ({len(data)} bytes)")
    return 0


def cmd_calibrate(_args: argparse.Namespace) -> int:
    print("calibrate: not implemented yet (needs known-resistor measurements).")
    print("See docs/eit-bioimpedance/eit-netlist.md section 8 step 7.")
    return 0


def _open_hardware():
    from software import pipeline
    from software.core import config

    hardware = pipeline.default_hardware()
    hardware.open(config.device_config())
    return hardware


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dev.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="report backends and dependencies").set_defaults(func=cmd_doctor)

    p_scan = sub.add_parser("scan-once", help="run one scan to a PNG file")
    p_scan.add_argument("-o", "--output", help="output PNG path (default ./scan.png)")
    p_scan.set_defaults(func=cmd_scan_once)

    sub.add_parser("calibrate", help="gain/phase calibration").set_defaults(func=cmd_calibrate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
