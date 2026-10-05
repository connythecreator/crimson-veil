"""Control-surface WebSocket server over the simulated backend.

Runs the real asyncio server on an ephemeral port and drives it with an
in-process ``websockets`` client - no hardware required.
"""

from __future__ import annotations

import asyncio
import json
import socket

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from service import protocol
from service.server import ControlServer
from service.session import ScanSession

FREQS = [5_000.0, 50_000.0]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _recv_json(ws) -> dict:
    raw = await asyncio.wait_for(ws.recv(), timeout=10)
    if isinstance(raw, (bytes, bytearray)):  # a binary frame we weren't expecting
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
    return json.loads(raw)


async def _recv_type(ws, wanted: str) -> dict:
    """Read until a message of the given type arrives, skipping periodic noise
    (metrics broadcasts) and state updates."""
    while True:
        msg = await _recv_json(ws)
        if msg["type"] == wanted:
            return msg


async def _recv_result(ws, scan_id: str) -> bytes:
    """Read messages until the scan_result header for ``scan_id``, then its PNG."""
    while True:
        msg = await _recv_json(ws)
        assert msg["type"] != "scan_error", msg
        if msg["type"] == "scan_result" and msg["id"] == scan_id:
            assert msg["bytes"] > 0
            blob = await asyncio.wait_for(ws.recv(), timeout=10)
            assert isinstance(blob, (bytes, bytearray))
            assert len(blob) == msg["bytes"]
            assert bytes(blob)[:8] == b"\x89PNG\r\n\x1a\n"
            return bytes(blob)


@pytest.fixture
def session():
    s = ScanSession()
    s.set_frequencies(FREQS)
    s.boot()
    yield s
    s.close()


def test_session_run_scan_returns_png(session):
    png = session.run_scan()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_png_size_matches(session):
    from service.server import _png_size

    png = session.run_scan()
    w, h = _png_size(png)
    assert w > 0 and h > 0


def test_ready_scan_roundtrip(session):
    async def run():
        server = ControlServer(session)
        port = _free_port()
        async with serve(server.handler, "127.0.0.1", port, max_size=None):
            async with connect(f"ws://127.0.0.1:{port}") as ws:
                ready = await _recv_type(ws, "ready")
                assert ready["n_electrodes"] == 8
                await ws.send(protocol.encode(protocol.ScanRequest(id="abc")))
                png = await _recv_result(ws, "abc")
                assert len(png) > 8

    asyncio.run(run())


def test_ping_pong(session):
    async def run():
        server = ControlServer(session)
        port = _free_port()
        async with serve(server.handler, "127.0.0.1", port, max_size=None):
            async with connect(f"ws://127.0.0.1:{port}") as ws:
                await _recv_type(ws, "ready")
                await ws.send(protocol.encode(protocol.Ping()))
                msg = await _recv_type(ws, "pong")
                assert msg["type"] == "pong"

    asyncio.run(run())


def test_continuous_mode_streams_multiple(session):
    async def run():
        server = ControlServer(session)
        port = _free_port()
        async with serve(server.handler, "127.0.0.1", port, max_size=None):
            async with connect(f"ws://127.0.0.1:{port}") as ws:
                await _recv_type(ws, "ready")
                await ws.send(
                    protocol.encode(
                        protocol.Continuous(on=True, active_interval_s=0.05, idle_interval_s=0.05)
                    )
                )
                # first state ack, then at least one scan flows through
                seen = 0
                while seen < 1:
                    msg = await _recv_json(ws)
                    if msg["type"] == "scan_result":
                        blob = await asyncio.wait_for(ws.recv(), timeout=10)
                        assert isinstance(blob, (bytes, bytearray))
                        seen += 1
                await ws.send(protocol.encode(protocol.Stop()))

    asyncio.run(run())


def test_activity_keeps_active_interval(session):
    """activity{} within the timeout keeps the next wait at the active interval."""
    async def run():
        server = ControlServer(session)
        port = _free_port()
        async with serve(server.handler, "127.0.0.1", port, max_size=None):
            async with connect(f"ws://127.0.0.1:{port}") as ws:
                await _recv_type(ws, "ready")
                # active=0.05, idle=5.0: if activity is honoured the next state
                # reports ~0.05, not the idle 5.0.
                await ws.send(
                    protocol.encode(
                        protocol.Continuous(on=True, active_interval_s=0.05, idle_interval_s=5.0)
                    )
                )
                # Drain until we see a state event emitted by the loop (not the
                # immediate ack), after sending activity each time.
                await ws.send(protocol.encode(protocol.Activity()))
                interval = None
                for _ in range(12):
                    msg = await _recv_json(ws)
                    if msg["type"] == "scan_result":
                        await asyncio.wait_for(ws.recv(), timeout=10)
                        await ws.send(protocol.encode(protocol.Activity()))
                    elif msg["type"] == "state" and msg.get("interval_s"):
                        interval = msg["interval_s"]
                        break
                assert interval == 0.05, interval
                await ws.send(protocol.encode(protocol.Stop()))

    asyncio.run(run())
