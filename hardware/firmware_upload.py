"""Upload the MicroPython firmware to the ESP32.

The ESP32 runs MicroPython, so "flashing" here means copying the source files
to the device's filesystem (via ``mpremote``) and resetting it. The generated
``board_config.py`` selects the real or mock front end.

Install the uploader with ``pip install mpremote`` (device dependency); it is
listed in ``requirements-pi.txt``. The caller must release the serial port
first (the control service closes its ``ScanSession`` before calling this).
"""

from __future__ import annotations

import glob
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "firmware" / "mp-firm" / "src"
FIRMWARE_FILES = ("main.py", "protocol.py", "ad5933_driver.py", "mock_ad5933.py")


def find_port(preferred: str | None = None) -> str:
    """Return the configured port, or the first ttyACM*/ttyUSB* adapter."""
    if preferred:
        return preferred
    candidates = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    if not candidates:
        raise RuntimeError("no ESP32 serial port found (/dev/ttyACM* or /dev/ttyUSB*)")
    return candidates[0]


def _mpremote_command() -> list[str]:
    """Prefer the venv's console script, then PATH, then ``python -m mpremote``."""
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
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")


def upload_firmware(
    port: str | None = None,
    *,
    mock: bool = False,
    source_dir: str | Path | None = None,
) -> dict:
    """Copy the firmware files to the ESP32 and reset it.

    Returns ``{"port", "files", "mock"}``. Raises on a missing port/file or an
    ``mpremote`` failure.
    """
    source = Path(source_dir) if source_dir else DEFAULT_SOURCE
    missing = [name for name in FIRMWARE_FILES if not (source / name).is_file()]
    if missing:
        raise RuntimeError(f"firmware files missing under {source}: {', '.join(missing)}")

    target_port = find_port(port)
    mpremote = _mpremote_command()

    with tempfile.TemporaryDirectory(prefix="cv-firmware-") as tmp:
        config = Path(tmp) / "board_config.py"
        config.write_text(f"USE_MOCK = {bool(mock)!r}\n")

        files = list(FIRMWARE_FILES) + ["board_config.py"]
        for name in files:
            local = config if name == "board_config.py" else source / name
            _run([*mpremote, "connect", target_port, "fs", "cp", str(local), f":{name}"])

    # A soft reset can stop at the REPL and never run main.py; do a hard reset.
    # The reset drops the mpremote link, so a nonzero/timeout result is normal.
    try:
        subprocess.run(
            [
                *mpremote,
                "connect",
                target_port,
                "exec",
                "import machine; machine.reset()",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        pass
    return {"port": target_port, "files": files, "mock": bool(mock)}
