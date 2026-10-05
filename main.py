#!/usr/bin/env python3
"""Crimson Veil - device entrypoint (headless / service).

Boots the control service, which owns the hardware and solver backends and
serves scans to the native kiosk (`kiosk-rs`) over a localhost WebSocket:

    python main.py                 # ws://127.0.0.1:8765
    python main.py --port 9000

The graphical front end is now the Rust kiosk, not Python. On the device this
runs as `crimson-veil-backend.service`; `setup-pi-kiosk.sh` wires it up. For
development tooling (doctor, scan-once, calibrate) see `dev.py`.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def main() -> int:
    from service.server import main as server_main

    return server_main()


if __name__ == "__main__":
    raise SystemExit(main())
