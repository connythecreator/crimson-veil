#!/usr/bin/env python3
"""Run the standalone Crimson Veil bench-test firmware from this computer.

The ESP32 is connected directly to this machine over USB. This tool does not
use the Raspberry Pi, the control service, the kiosk, pyEIT or any repository
backend code: it uploads the self-contained ``firmware/mp-firm/hwtest`` tree
(optional) and talks line-delimited JSON to the ESP32 over serial.

Examples:
    python tools/hwtest.py --upload --port /dev/ttyUSB0
    python tools/hwtest.py --port /dev/ttyUSB0
    python tools/hwtest.py --port /dev/ttyUSB0 --f 10000 --json
    python tools/hwtest.py --port /dev/ttyUSB0 --calibrate --freqs 10000,50000
"""

from __future__ import annotations

import argparse
import glob
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HWTEST_DIR = ROOT / "firmware" / "mp-firm" / "hwtest"
HWTEST_FILES = ("main.py", "hwtest_core.py", "ad5933_driver.py")

DEFAULT_BAUD = 115200
DEFAULT_FREQ_HZ = 50_000.0
DEFAULT_CAPACITANCE_F = 0.1e-6
DEFAULT_SAMPLES = 16
DEFAULT_TOL_PCT = 5.0
DEFAULT_TOL_DEG = 5.0
DEFAULT_DRIFT_PCT = 2.0
DEFAULT_DRIFT_DEG = 2.0


class HwTestError(RuntimeError):
    pass


class LineSerial:
    """Small pyserial wrapper that returns whole lines and skips boot noise."""

    def __init__(self, port: str, baud: int, timeout: float) -> None:
        import serial  # imported lazily so --help works without pyserial

        self._serial = serial.Serial(port=port, baudrate=baud, timeout=timeout)
        self._buffer = bytearray()

    def write_line(self, message: dict) -> None:
        self._serial.write((json.dumps(message) + "\n").encode("utf-8"))
        self._serial.flush()

    def read_line(self, timeout: float) -> str | None:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                raw = bytes(self._buffer[:newline])
                del self._buffer[:newline + 1]
                return raw.decode("utf-8", "replace").strip()
            self._serial.timeout = max(0.0, deadline - time.monotonic())
            raw = self._serial.readline()
            if not raw:
                return None
            self._buffer.extend(raw)
            if b"\n" not in self._buffer and time.monotonic() >= deadline:
                return None

    def close(self) -> None:
        self._serial.close()


def find_port(preferred: str | None = None) -> str:
    """Find the ESP32, preferring CP210x/CH340/Espressif adapters.

    A machine may also have an Arduino or another CDC device attached. The
    ``/dev/serial/by-id`` names let us skip the Arduino instead of blindly
    taking the first ``ttyACM*``.
    """
    if preferred:
        return preferred

    by_id = Path("/dev/serial/by-id")
    links = sorted(by_id.iterdir()) if by_id.is_dir() else []
    preferred_markers = ("cp210", "ch340", "espressif", "silicon_labs", "wch")
    for link in links:
        name = link.name.lower()
        if any(marker in name for marker in preferred_markers):
            return str(link.resolve())
    for link in links:
        name = link.name.lower()
        if "arduino" not in name:
            return str(link.resolve())

    candidates = sorted(glob.glob("/dev/ttyUSB*")) + sorted(glob.glob("/dev/ttyACM*"))
    if not candidates:
        raise HwTestError("no ESP32 serial port found (pass --port explicitly)")
    return candidates[0]


def _mpremote_command() -> list[str]:
    local = Path(sys.executable).with_name("mpremote")
    if local.is_file():
        return [str(local)]
    found = shutil.which("mpremote")
    if found:
        return [found]
    return [sys.executable, "-m", "mpremote"]


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise HwTestError(f"{' '.join(command)} failed: {detail}")


def upload(port: str) -> list[str]:
    """Copy the standalone hwtest firmware to the ESP32 and reset it."""
    missing = [name for name in HWTEST_FILES if not (HWTEST_DIR / name).is_file()]
    if missing:
        raise HwTestError(f"hwtest firmware files missing: {', '.join(missing)}")

    mpremote = _mpremote_command()
    for name in HWTEST_FILES:
        _run(
            [
                *mpremote,
                "connect",
                port,
                "fs",
                "cp",
                str(HWTEST_DIR / name),
                f":{name}",
            ]
        )

    # A soft reset can stop at the REPL and never run main.py; hard reset.
    try:
        subprocess.run(
            [
                *mpremote,
                "connect",
                port,
                "exec",
                "import machine; machine.reset()",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        pass
    return list(HWTEST_FILES)


def _read_message(serial: LineSerial, timeout: float) -> dict | None:
    line = serial.read_line(timeout)
    if line is None:
        raise HwTestError("serial read timed out")
    text = line.strip()
    if not text.startswith("{"):
        return None  # MicroPython REPL/boot noise
    try:
        message = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HwTestError(f"bad line from ESP32: {line!r}") from exc
    if not isinstance(message, dict) or "type" not in message:
        raise HwTestError(f"expected a JSON object with a 'type': {line!r}")
    return message


def wait_for(
    serial: LineSerial,
    kinds: tuple[str, ...],
    timeout: float,
    seq: int | None = None,
) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HwTestError(f"timed out waiting for {', '.join(kinds)}")
        message = _read_message(serial, remaining)
        if message is None:
            continue
        if message["type"] == "hwtest_error":
            raise HwTestError(str(message.get("message", "unknown ESP32 error")))
        if message["type"] not in kinds:
            continue
        if seq is not None and message.get("seq") != seq:
            continue
        return message


def run_test(serial: LineSerial, args: argparse.Namespace) -> dict:
    serial.write_line({"type": "hwtest_identify"})
    hello = wait_for(serial, ("hwtest_hello",), timeout=args.timeout)
    if not hello.get("firmware", "").startswith("hwtest"):
        raise HwTestError(f"unexpected firmware: {hello.get('firmware')!r}")

    serial.write_line(
        {
            "type": "hwtest_run",
            "seq": 1,
            "f": args.f,
            "c_f": args.c_f,
            "samples": args.samples,
            "tol_pct": args.tol_pct,
            "tol_deg": args.tol_deg,
            "drift_pct": args.drift_pct,
            "drift_deg": args.drift_deg,
        }
    )
    point_timeout = max(args.timeout, 1.0 + 0.5 * args.samples)
    return wait_for(serial, ("hwtest_result",), timeout=point_timeout, seq=1)


def _parse_freqs(text: str) -> list[float]:
    freqs = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            freq = float(part)
        except ValueError as exc:
            raise HwTestError(f"bad --freqs value: {part!r}") from exc
        if freq <= 0:
            raise HwTestError(f"--freqs values must be positive: {part!r}")
        freqs.append(freq)
    if not freqs:
        raise HwTestError("--freqs needs at least one frequency")
    return freqs


def run_calibration(
    serial: LineSerial, args: argparse.Namespace, freqs: list[float]
) -> dict:
    serial.write_line({"type": "hwtest_identify"})
    hello = wait_for(serial, ("hwtest_hello",), timeout=args.timeout)
    if not hello.get("firmware", "").startswith("hwtest"):
        raise HwTestError(f"unexpected firmware: {hello.get('firmware')!r}")

    serial.write_line(
        {
            "type": "hwtest_calibrate",
            "seq": 1,
            "freqs": freqs,
            "c_f": args.c_f,
            "samples": args.samples,
            "tol_pct": args.tol_pct,
            "tol_deg": args.tol_deg,
            "drift_pct": args.drift_pct,
            "drift_deg": args.drift_deg,
        }
    )
    timeout = max(args.timeout, 2.0 + 0.75 * args.samples * len(freqs))
    return wait_for(serial, ("hwtest_calibration",), timeout=timeout, seq=1)


def _fmt(value, unit: str = "", digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}{unit}"


def format_result(result: dict) -> str:
    expected = result.get("expected") or {}
    raw = result.get("raw") or {}
    calibration = result.get("calibration") or {}
    measured = result.get("measured") or {}
    drift = result.get("drift") or {}
    lines = [
        "Crimson Veil - bench hardware test",
        f"  firmware   : {result.get('firmware', '?')}",
        f"  frequency  : {_fmt(result.get('f_hz'), ' Hz', 0)}",
        f"  temperature: {_fmt(result.get('temp_ad5933_c'), ' C')}",
        f"  capacitor  : {_fmt((result.get('fixture') or {}).get('c_f'), ' F', 9)}",
        f"  expected   : {_fmt(expected.get('mag'), ' ohm')} @ "
        f"{_fmt(expected.get('phase_deg'), ' deg')}",
        f"  raw        : re {_fmt(raw.get('re_mean'))}  im {_fmt(raw.get('im_mean'))}  "
        f"(n={raw.get('n', 0)}, spread {_fmt(raw.get('mag_std_pct'), ' %')})",
        f"  calibration: K {_fmt(calibration.get('k_mag'), ' ohm/code')} @ "
        f"{_fmt(calibration.get('k_phase_deg'), ' deg')}",
        f"  measured   : {_fmt(measured.get('mag'), ' ohm')} @ "
        f"{_fmt(measured.get('phase_deg'), ' deg')}",
        f"  drift      : {_fmt(drift.get('mag_pct'), ' %')} / "
        f"{_fmt(drift.get('phase_deg'), ' deg')}",
        "  checks:",
    ]
    for item in result.get("checks", []):
        status = str(item.get("status", "?")).upper()
        detail = item.get("detail", "")
        lines.append(f"    [{status:4}] {item.get('name', '?'):12} {detail}")
    lines.append(f"  status     : {str(result.get('status', '?')).upper()}")
    if result.get("error"):
        lines.append(f"  error      : {result['error']}")
    return "\n".join(lines)


def format_calibration(result: dict) -> str:
    lines = [
        "Crimson Veil - calibration written",
        f"  file   : {result.get('file', '?')}",
        f"  status : {str(result.get('status', '?')).upper()}",
        "  entries:",
    ]
    for entry in result.get("entries", []):
        lines.append(
            f"    {_fmt(entry.get('f'), ' Hz', 0):>12}  "
            f"K {_fmt(entry.get('mag'), ' ohm/code')} @ "
            f"{_fmt(entry.get('phase_deg'), ' deg')}  "
            f"[{str(entry.get('status', '?')).upper()}]"
        )
    if result.get("error"):
        lines.append(f"  error  : {result['error']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools/hwtest.py",
        description="Standalone AD5933 bench test from this computer.",
    )
    parser.add_argument("--port", help="serial port (default: first ttyACM*/ttyUSB*)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--upload", action="store_true", help="upload hwtest firmware first")
    parser.add_argument("--upload-only", action="store_true", help="upload and exit")
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="measure multiple frequencies and write cal.json on the ESP32",
    )
    parser.add_argument(
        "--freqs",
        default="10000,50000",
        help="comma-separated calibration frequencies (default: 10000,50000)",
    )
    parser.add_argument("--f", type=float, default=DEFAULT_FREQ_HZ, help="test frequency (Hz)")
    parser.add_argument(
        "--c-f",
        type=float,
        default=DEFAULT_CAPACITANCE_F,
        help="fixture capacitance (F)",
    )
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--tol-pct", type=float, default=DEFAULT_TOL_PCT)
    parser.add_argument("--tol-deg", type=float, default=DEFAULT_TOL_DEG)
    parser.add_argument("--drift-pct", type=float, default=DEFAULT_DRIFT_PCT)
    parser.add_argument("--drift-deg", type=float, default=DEFAULT_DRIFT_DEG)
    parser.add_argument("--json", action="store_true", help="print the raw result JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.samples < 2:
        print("error: --samples must be at least 2", file=sys.stderr)
        return 2

    try:
        freqs = _parse_freqs(args.freqs) if args.calibrate else []
        port = find_port(args.port)
        if args.upload or args.upload_only:
            files = upload(port)
            print(f"uploaded to {port}: {', '.join(files)}")
            if args.upload_only:
                return 0
            time.sleep(1.0)

        serial = LineSerial(port, args.baud, args.timeout)
        try:
            if args.calibrate:
                result = run_calibration(serial, args, freqs)
            else:
                result = run_test(serial, args)
        finally:
            serial.close()
    except (HwTestError, OSError) as exc:
        print(f"hwtest failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2))
    elif args.calibrate:
        print(format_calibration(result))
    else:
        print(format_result(result))
    return 0 if result.get("status") in ("pass", "warn") else 1


if __name__ == "__main__":
    raise SystemExit(main())
