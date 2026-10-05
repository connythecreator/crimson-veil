"""Crimson Veil control surface.

A localhost WebSocket front end over :mod:`software.pipeline`, consumed by the
native ``kiosk-rs`` UI (and, later, any companion/web client). See
``service/README.md``.
"""

from __future__ import annotations

__all__ = ["protocol", "session", "server"]
