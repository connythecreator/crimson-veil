#!/usr/bin/env python3
"""Run the MicroPython firmware in mock mode over a pseudo-terminal.

The firmware's normal serial command loop is attached to the pty *master*; the
host opens the *slave* path (also exposed as ``--link``) with pyserial. This
exercises the real ``Esp32Hardware`` / ``SerialTransport`` path without an
ESP32, AD5933 or mux bank.
"""

from __future__ import annotations

import argparse
import os
import pty
import subprocess
import sys
import tty
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIRMWARE = ROOT / "firmware" / "mp-firm" / "src" / "main.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/run_mock_firmware.py")
    parser.add_argument(
        "--firmware", default=str(DEFAULT_FIRMWARE), help="firmware main.py path"
    )
    parser.add_argument(
        "--link",
        default="/tmp/cv-mock-tty",
        help="symlink the host can use as CV_ESP32_PORT ('' to disable)",
    )
    args = parser.parse_args(argv)

    firmware = Path(args.firmware)
    if not firmware.is_file():
        parser.error(f"firmware not found: {firmware}")

    master, slave = pty.openpty()
    tty.setraw(slave)
    slave_name = os.ttyname(slave)

    link = args.link or None
    if link:
        try:
            os.unlink(link)
        except FileNotFoundError:
            pass
        os.symlink(slave_name, link)

    serial_path = link or slave_name
    print(f"mock firmware pty : {slave_name}", flush=True)
    if link:
        print(f"host serial path  : {link}", flush=True)
    print("start the service with:", flush=True)
    print(
        f"  CV_BACKEND=esp32 CV_SOLVER=pyeit CV_ESP32_PORT={serial_path} "
        "python -m service.server",
        flush=True,
    )

    # stdin/stdout/stderr all on the master: the firmware talks the JSON
    # protocol to whatever opens the slave path. The parent keeps `slave` open
    # so writes to the master do not fail with EIO before the host connects.
    proc = subprocess.Popen(
        [sys.executable, "-u", str(firmware), "--mock"],
        stdin=master,
        stdout=master,
        stderr=master,
        close_fds=True,
    )
    try:
        return proc.wait()
    finally:
        if link:
            try:
                os.unlink(link)
            except FileNotFoundError:
                pass
        os.close(master)
        os.close(slave)


if __name__ == "__main__":
    raise SystemExit(main())
