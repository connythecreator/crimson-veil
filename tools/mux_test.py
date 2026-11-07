#!/usr/bin/env python3
"""Run the firmware mux continuity test against a connected ESP32.

On the full 8-electrode build every electrode 0-7 should read connected. All
four roles are driven to the same electrode; the optional ``--d-neg`` override
is only for the old C0/C1 diagnostic workaround. Sense+ must follow Drive+ (and
Sense− Drive−) for a valid measurement; do not reverse the sense pair. Use
``--expect 0`` for the old single-electrode bench check.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hardware.esp32 import SerialTransport, _preferred_serial_port  # noqa: E402


def _read_until(transport, kind, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = transport.read_line(0.5)
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if message.get("type") == "error":
            raise RuntimeError(message.get("message", "unknown firmware error"))
        if message.get("type") == "hwtest_hello":
            raise RuntimeError(
                "ESP32 is running the bench hwtest firmware; upload the "
                "production firmware with 'python dev.py upload-firmware'"
            )
        if message.get("type") == kind:
            return message
    raise TimeoutError(f"timed out waiting for {kind}")


def _print_result(result):
    print(
        f"mux test at {result['frequency_hz']:.0f} Hz, "
        f"d_neg={result.get('d_neg')}, min_raw={result['min_raw']}, "
        f"calibration={result['calibration']}"
    )
    print("  e  d-  status      raw|S|       |Z|")
    for point in result["points"]:
        z_abs = point.get("z_abs")
        z_text = "-" if z_abs is None else f"{z_abs:.2f}"
        print(
            f"  {point['e']:1d}  {point['drive_neg']:1d}  "
            f"{point['status']:<9} {point['raw_abs']:10.1f}  {z_text:>10}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="serial port (default: auto-detect ESP32)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--f", type=float, default=50_000.0)
    parser.add_argument("--min-raw", type=float, default=10.0)
    parser.add_argument(
        "--d-neg",
        type=int,
        default=None,
        help="optional D- electrode override (default: same as the tested electrode)",
    )
    parser.add_argument(
        "--expect",
        choices=("all", "0"),
        default="all",
        help="expected connected set: all electrodes (default) or only electrode 0",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    parser.add_argument(
        "--no-check", action="store_true", help="print the table without pass/fail"
    )
    args = parser.parse_args()

    port = args.port or _preferred_serial_port()
    if not port:
        print("no ESP32 serial port found", file=sys.stderr)
        return 2

    transport = SerialTransport(port, args.baud, 2.0)
    try:
        transport.write_line(json.dumps({"type": "identify"}))
        _read_until(transport, "hello", 5.0)
        request = {
            "type": "mux_test",
            "f": args.f,
            "min_raw": args.min_raw,
        }
        if args.d_neg is not None:
            request["d_neg"] = args.d_neg
        transport.write_line(json.dumps(request))
        result = _read_until(transport, "mux_test_result", args.timeout)
    except (RuntimeError, TimeoutError, OSError) as exc:
        print(f"mux test failed: {exc}", file=sys.stderr)
        return 2
    finally:
        transport.close()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_result(result)

    if args.no_check:
        return 0

    connected = [point["e"] for point in result["points"] if point["status"] == "connected"]
    if args.expect == "all":
        open_electrodes = [
            point["e"] for point in result["points"] if point["status"] == "open"
        ]
        if open_electrodes:
            print(
                "FAIL: open electrode(s): "
                + ", ".join(str(electrode) for electrode in open_electrodes),
                file=sys.stderr,
            )
            return 1
        print("PASS: all electrodes 0-7 are connected")
        return 0

    if connected != [0]:
        print(
            f"FAIL: expected only electrode 0 connected, got {connected}",
            file=sys.stderr,
        )
        return 1
    print("PASS: only electrode 0 is connected; electrodes 1-7 are open")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
