"""Crimson Veil control-surface WebSocket server.

Owns the scan pipeline and exposes it to the kiosk (and, later, any companion
front end) over a localhost WebSocket. Run as a systemd service on the device::

    python -m service.server --host 127.0.0.1 --port 8765

Design:

* one :class:`~service.session.ScanSession` holds the boot-opened backends;
* blocking pipeline work runs via :func:`asyncio.to_thread`, never on the loop;
* a scan is single-flight (``BusyError`` -> ``scan_error``);
* continuous mode is driven here, not by the client: after each scan the server
  schedules the next one ``interval_s`` later, until ``stop`` / disconnect.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import struct
import time
import uuid

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from . import metrics, protocol
from .session import BusyError, ScanSession

log = logging.getLogger("crimson-veil.service")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
# Debounce: scan every ACTIVE interval while the user is interacting, and back
# off to the IDLE interval after ACTIVITY_TIMEOUT_S of quiet.
DEFAULT_ACTIVE_INTERVAL_S = 60.0
DEFAULT_IDLE_INTERVAL_S = 120.0
ACTIVITY_TIMEOUT_S = 30.0
METRICS_INTERVAL_S = 5.0


def _png_size(data: bytes) -> tuple[int, int]:
    """Read width/height from a PNG IHDR (no third-party image deps)."""
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return (0, 0)
    width, height = struct.unpack(">II", data[16:24])
    return (width, height)


class ControlServer:
    def __init__(self, session: ScanSession) -> None:
        self._session = session
        # Serialise sends to each client and keep binary/JSON ordering intact.
        self._send_locks: dict[ServerConnection, asyncio.Lock] = {}

    async def _send_json(self, ws: ServerConnection, message) -> None:
        lock = self._send_locks.setdefault(ws, asyncio.Lock())
        async with lock:
            await ws.send(protocol.encode(message))

    async def _send_result(self, ws: ServerConnection, scan_id: str, png: bytes) -> None:
        width, height = _png_size(png)
        header = protocol.ScanResult(id=scan_id, width=width, height=height, bytes=len(png))
        lock = self._send_locks.setdefault(ws, asyncio.Lock())
        async with lock:
            await ws.send(protocol.encode(header))
            await ws.send(png)

    async def _run_scan(self, ws: ServerConnection, scan_id: str) -> None:
        try:
            png = await asyncio.to_thread(
                self._session.run_scan,
                lambda _msg: None,
            )
        except BusyError:
            await self._send_json(
                ws, protocol.ScanError(id=scan_id, message="busy: scan in progress")
            )
            return
        except Exception as exc:  # noqa: BLE001 - report to the client
            await self._send_json(
                ws, protocol.ScanError(id=scan_id, message=f"{type(exc).__name__}: {exc}")
            )
            return
        await self._send_result(ws, scan_id, png)

    async def handler(self, ws: ServerConnection) -> None:
        self._send_locks[ws] = asyncio.Lock()
        log.info("client connected: %s", getattr(ws, "remote_address", "?"))
        continuous = False
        scan_task: asyncio.Task | None = None
        metrics_task: asyncio.Task | None = None
        active_interval_s = DEFAULT_ACTIVE_INTERVAL_S
        idle_interval_s = DEFAULT_IDLE_INTERVAL_S
        last_activity = time.monotonic()
        try:
            # Announce boot status immediately.
            if self._session.booted:
                await self._send_json(ws, protocol.Ready(**self._session.ready_payload()))
            elif self._session.boot_error:
                await self._send_json(ws, protocol.BootError(message=self._session.boot_error))

            async def schedule_scan(scan_id: str) -> None:
                await self._run_scan(ws, scan_id)

            async def metrics_loop() -> None:
                while True:
                    snap = metrics.snapshot(self._session.hardware)
                    await self._send_json(ws, protocol.Metrics(**snap))
                    await asyncio.sleep(METRICS_INTERVAL_S)

            metrics_task = asyncio.create_task(metrics_loop())

            async def continuous_loop() -> None:
                # Debounced: run a scan, wait active/idle interval, repeat.
                while True:
                    if self._session.booted:
                        await self._run_scan(ws, uuid.uuid4().hex)
                    recent = (time.monotonic() - last_activity) < ACTIVITY_TIMEOUT_S
                    interval = active_interval_s if recent else idle_interval_s
                    await self._send_json(
                        ws, protocol.State(continuous=True, scanning=False, interval_s=interval)
                    )
                    await asyncio.sleep(interval)

            async for raw in ws:
                if isinstance(raw, (bytes, bytearray)):
                    log.debug("ignoring unexpected binary frame (%d bytes)", len(raw))
                    continue
                try:
                    msg = protocol.decode(raw)
                except (ValueError, UnicodeDecodeError) as exc:
                    log.warning("bad message: %s", exc)
                    continue

                kind = msg.get("type")
                if kind == "hello":
                    log.info("hello from %s (protocol %s)", msg.get("client"), msg.get("protocol"))
                    if self._session.booted:
                        await self._send_json(ws, protocol.Ready(**self._session.ready_payload()))
                elif kind == "scan":
                    if scan_task and not scan_task.done():
                        await self._send_json(
                            ws,
                            protocol.ScanError(
                                id=msg.get("id", ""), message="busy: scan in progress"
                            ),
                        )
                    else:
                        scan_id = msg.get("id") or uuid.uuid4().hex
                        scan_task = asyncio.create_task(schedule_scan(scan_id))
                elif kind == "continuous":
                    want = bool(msg.get("on", True))
                    active_interval_s = float(
                        msg.get("active_interval_s", active_interval_s)
                    )
                    idle_interval_s = float(msg.get("idle_interval_s", idle_interval_s))
                    if want and not continuous:
                        continuous = True
                        last_activity = time.monotonic()
                        scan_task = asyncio.create_task(continuous_loop())
                    elif not want and continuous:
                        continuous = False
                        if scan_task:
                            scan_task.cancel()
                            scan_task = None
                    await self._send_json(
                        ws,
                        protocol.State(
                            continuous=continuous,
                            scanning=bool(scan_task),
                            interval_s=active_interval_s,
                        ),
                    )
                elif kind == "activity":
                    last_activity = time.monotonic()
                elif kind == "stop":
                    continuous = False
                    if scan_task:
                        scan_task.cancel()
                        scan_task = None
                    await self._send_json(
                        ws, protocol.State(continuous=False, scanning=False, interval_s=0.0)
                    )
                elif kind == "set_frequency":
                    try:
                        self._session.set_frequency(float(msg.get("frequency_hz", 0.0)))
                        await self._send_json(ws, protocol.Ready(**self._session.ready_payload()))
                    except ValueError as exc:
                        await self._send_json(ws, protocol.ScanError(id="", message=str(exc)))
                elif kind == "ping":
                    await self._send_json(ws, protocol.Pong())
                else:
                    log.warning("unknown message type: %r", kind)
        except ConnectionClosed:
            log.info("client disconnected (socket closed)")
        finally:
            # Stop any continuous scheduler still holding this socket, then
            # wait briefly so its in-flight send does not outlive the handler.
            for task in (scan_task, metrics_task):
                if task is not None:
                    task.cancel()
                    with contextlib.suppress(BaseException):
                        await task
            self._send_locks.pop(ws, None)
            log.info("client handler finished")


async def _amain(host: str, port: int) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    session = ScanSession()
    try:
        identity = session.boot()
        log.info("backends ready: %s", identity)
    except Exception as exc:  # noqa: BLE001 - keep serving so clients see boot_error
        log.error("backend boot failed: %s", exc)

    server = ControlServer(session)
    async with serve(server.handler, host, port, max_size=None):
        log.info("listening on ws://%s:%d", host, port)
        try:
            await asyncio.Future()  # run forever
        finally:
            session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="service.server", description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_amain(args.host, args.port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
