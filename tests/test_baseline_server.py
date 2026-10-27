"""Measured-baseline commands through the real control-service WebSocket."""

from __future__ import annotations

import asyncio
import json
import threading

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from service import protocol
from service.server import ControlServer
from service.session import ScanSession
from software.core import config


@pytest.fixture
def session(monkeypatch):
    monkeypatch.setattr(config, "HARDWARE_BACKEND", "sim")
    monkeypatch.setattr(config, "SOLVER_BACKEND", "stub")
    instance = ScanSession()
    instance.boot()
    yield instance
    instance.close()


async def recv_type(ws, kind):
    async with asyncio.timeout(10):
        while True:
            raw = await ws.recv()
            if isinstance(raw, str):
                message = json.loads(raw)
                if message["type"] == kind:
                    return message


def test_capture_baseline_then_scan_and_frequency_invalidation(session):
    async def run():
        async with serve(ControlServer(session).handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}") as ws:
                ready = await recv_type(ws, "ready")
                assert ready["baseline_ready"] is False
                await ws.send(protocol.encode(protocol.CaptureBaseline(id="reference")))
                captured = await recv_type(ws, "baseline_captured")
                assert captured == {
                    "type": "baseline_captured",
                    "id": "reference",
                    "frequency_hz": ready["frequency_hz"],
                    "n_electrodes": ready["n_electrodes"],
                }
                assert (await recv_type(ws, "ready"))["baseline_ready"] is True
                await ws.send(protocol.encode(protocol.ScanRequest(id="target")))
                result = await recv_type(ws, "scan_result")
                assert result["id"] == "target"
                image = await asyncio.wait_for(ws.recv(), timeout=10)
                assert image.startswith(b"\x89PNG\r\n\x1a\n")
                assert len(image) == result["bytes"]
                await ws.send(protocol.encode(protocol.SetFrequency(frequency_hz=40_000)))
                changed = await recv_type(ws, "ready")
                assert changed["frequency_hz"] == 40_000
                assert changed["baseline_ready"] is False

    asyncio.run(run())


def test_capture_blocks_other_operations_and_keeps_socket_responsive(session, monkeypatch):
    started, release = threading.Event(), threading.Event()
    original_scan = session.hardware.scan

    def blocking_scan():
        started.set()
        if not release.wait(timeout=10):
            raise TimeoutError("test did not release acquisition")
        return original_scan()

    monkeypatch.setattr(session.hardware, "scan", blocking_scan)

    async def run():
        async with serve(ControlServer(session).handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}") as ws:
                await recv_type(ws, "ready")
                await ws.send(protocol.encode(protocol.CaptureBaseline(id="reference")))
                assert await asyncio.to_thread(started.wait, 5)
                try:
                    for command, request_id in (
                        (protocol.CaptureBaseline(id="duplicate"), "duplicate"),
                        (protocol.ScanRequest(id="target"), "target"),
                        (protocol.Continuous(on=True), ""),
                    ):
                        await ws.send(protocol.encode(command))
                        error = await recv_type(ws, "scan_error")
                        assert error["id"] == request_id
                        assert "busy" in error["message"]
                    await ws.send(protocol.encode(protocol.SetFrequency(frequency_hz=40_000)))
                    error = await recv_type(ws, "scan_error")
                    assert error["id"] == ""
                    assert session.frequency_hz != 40_000
                    await ws.send(protocol.encode(protocol.Ping()))
                    await recv_type(ws, "pong")

                    # The session lock also protects hardware across connections.
                    async with connect(f"ws://127.0.0.1:{port}") as other:
                        await recv_type(other, "ready")
                        await other.send(protocol.encode(protocol.CaptureBaseline(id="other")))
                        error = await recv_type(other, "scan_error")
                        assert error["id"] == "other"
                        assert "busy" in error["message"]
                finally:
                    release.set()
                assert (await recv_type(ws, "baseline_captured"))["id"] == "reference"

    asyncio.run(run())


def test_capture_failure_is_reported_and_can_be_retried(session, monkeypatch):
    original_capture = session.capture_baseline

    def fail():
        raise ValueError("reference acquisition failed")

    monkeypatch.setattr(session, "capture_baseline", fail)

    async def run():
        async with serve(ControlServer(session).handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}") as ws:
                await recv_type(ws, "ready")
                await ws.send(protocol.encode(protocol.CaptureBaseline(id="failed")))
                error = await recv_type(ws, "scan_error")
                assert error["id"] == "failed"
                assert "reference acquisition failed" in error["message"]
                assert not session.baseline_ready
                monkeypatch.setattr(session, "capture_baseline", original_capture)
                await ws.send(protocol.encode(protocol.CaptureBaseline(id="retry")))
                assert (await recv_type(ws, "baseline_captured"))["id"] == "retry"
                assert (await recv_type(ws, "ready"))["baseline_ready"] is True

    asyncio.run(run())
