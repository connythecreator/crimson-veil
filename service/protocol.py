"""Wire protocol for the Crimson Veil control surface.

The kiosk (a native Rust/eframe front end) talks to this service over a
localhost WebSocket. Control messages are JSON text frames; scan images are
sent as a binary frame *immediately after* the JSON header that announces them
(``scan_result``), so the pairing is order-preserving and the PNG is never
base64-inflated.

This module is the single source of truth for the message shapes, used by both
the server and the tests. The Rust side mirrors these types in
``kiosk-rs/src/protocol.rs`` - keep the two in step.

Client -> service messages::

    {"type": "hello", "client": str, "protocol": int}
    {"type": "scan", "id": str}
    {"type": "continuous", "on": bool,
     "active_interval_s": float, "idle_interval_s": float}
    {"type": "activity"}                      # user interaction; sets active state
    {"type": "stop"}
    {"type": "set_freqs", "frequencies_hz": [float, ...]}
    {"type": "ping"}

Service -> client messages::

    {"type": "ready", "backend": str, "solver": str,
     "n_electrodes": int, "frequencies_hz": [float, ...]}
    {"type": "boot_error", "message": str}
    {"type": "progress", "id": str, "message": str}
    {"type": "scan_result", "id": str, "width": int, "height": int, "bytes": int}
        followed by one binary frame containing the PNG bytes
    {"type": "scan_error", "id": str, "message": str}
    {"type": "state", "continuous": bool, "scanning": bool, "interval_s": float}
    {"type": "metrics", "battery_pct": float|null, "battery_charging": bool,
     "temp_c": float|null}
    {"type": "pong"}

Continuous mode debounces between scans: after each scan the service waits
``active_interval_s`` if the client has been active recently, otherwise
``idle_interval_s`` (see ``ACTIVITY_TIMEOUT_S`` in ``server.py``).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

PROTOCOL_VERSION = 1


# --- client -> service -----------------------------------------------------


@dataclass
class Hello:
    client: str = "kiosk-rs"
    protocol: int = PROTOCOL_VERSION
    type: str = field(default="hello", init=False)


@dataclass
class ScanRequest:
    id: str = ""
    type: str = field(default="scan", init=False)


@dataclass
class Continuous:
    on: bool = True
    active_interval_s: float = 60.0
    idle_interval_s: float = 120.0
    type: str = field(default="continuous", init=False)


@dataclass
class Activity:
    type: str = field(default="activity", init=False)


@dataclass
class Stop:
    type: str = field(default="stop", init=False)


@dataclass
class SetFreqs:
    frequencies_hz: list[float] = field(default_factory=list)
    type: str = field(default="set_freqs", init=False)


@dataclass
class Ping:
    type: str = field(default="ping", init=False)


# --- service -> client -----------------------------------------------------


@dataclass
class Ready:
    backend: str
    solver: str
    n_electrodes: int
    frequencies_hz: list[float]
    type: str = field(default="ready", init=False)


@dataclass
class BootError:
    message: str
    type: str = field(default="boot_error", init=False)


@dataclass
class Progress:
    id: str
    message: str
    type: str = field(default="progress", init=False)


@dataclass
class ScanResult:
    id: str
    width: int
    height: int
    bytes: int
    type: str = field(default="scan_result", init=False)


@dataclass
class ScanError:
    id: str
    message: str
    type: str = field(default="scan_error", init=False)


@dataclass
class State:
    continuous: bool
    scanning: bool
    interval_s: float = 0.0
    type: str = field(default="state", init=False)


@dataclass
class Metrics:
    battery_pct: float | None = None
    battery_charging: bool = False
    temp_c: float | None = None
    type: str = field(default="metrics", init=False)


@dataclass
class Pong:
    type: str = field(default="pong", init=False)


def encode(message: Any) -> str:
    """Serialise a protocol dataclass to a JSON text frame."""
    return json.dumps(asdict(message), separators=(",", ":"))


def decode(raw: str | bytes) -> dict:
    """Parse an incoming JSON text frame into a plain dict."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError("protocol message must be a JSON object with a 'type'")
    return data
